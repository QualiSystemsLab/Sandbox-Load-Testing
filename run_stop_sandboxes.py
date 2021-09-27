from sb_rest.sandbox_rest_api import SandboxRest
from timeit import default_timer
from time import time, sleep
import json
from common import SandboxErrorData, get_config_data, get_json_from_nested_obj, RunConfig
from logger import get_logger
import my_globals
import os
from datetime import datetime


def _get_latest_json_log_timestamp(blueprint_id):
    """
    find latest dated log in results folder
    sample results file name - <time_stamp>_<blueprint_name>.<filetype>
    :param str blueprint_id: refers to folder inside json-results
    :return:
    """
    current_dir = os.getcwd()
    log_folder_path = os.path.join(current_dir, my_globals.JSON_RESULTS_FOLDER, blueprint_id)
    log_files = os.listdir(log_folder_path)
    time_stamp_strings = ["_".join(x.split("_")[:-1]) for x in log_files]
    datetime_time_stamps = [datetime.strptime(ts, my_globals.TIMESTAMP_FORMATTING) for ts in time_stamp_strings]
    datetime_time_stamps.sort()
    latest_timestamp = datetime_time_stamps.pop()
    latest_timestamp_str = datetime.strftime(latest_timestamp, my_globals.TIMESTAMP_FORMATTING)
    return latest_timestamp_str


def build_log_path(time_stamp, blueprint_id, is_json_log=False):
    """
    find latest dated log in results folder
    sample results file name - <time_stamp>_<blueprint_name>.<filetype>
    :param str blueprint_id: refers to folder inside json-results
    :return:
    """
    if is_json_log:
        folder_name = my_globals.JSON_RESULTS_FOLDER
        file_type = "json"
    else:
        folder_name = my_globals.LOGS_FOLDER
        file_type = "log"

    current_dir = os.getcwd()
    log_folder_path = os.path.join(current_dir, folder_name, blueprint_id)
    log_file_name = "{}_{}.{}".format(time_stamp, blueprint_id, file_type)
    log_file_path = os.path.join(log_folder_path, log_file_name)
    return log_file_path


def _get_sandbox_data_from_json(path):
    with open(path) as config_file:
        data = json.load(config_file)
    obj_wrapped_data = [SandboxErrorData(sandbox_id=x["sandbox_id"],
                                         failed_setup_stage=x["failed_setup_stage"],
                                         setup_errors=x["setup_errors"])
                        for x in data]
    return obj_wrapped_data


def stop_sandboxes(sb_rest, run_config, time_stamp, logger):
    """
    :param SandboxRest sb_rest:
    :param RunConfig run_config:
    :param str time_stamp:
    :param logging.Logger logger:
    :return:
    """
    json_file_path = build_log_path(time_stamp, run_config.blueprint_id, is_json_log=True)
    sandbox_data_list = _get_sandbox_data_from_json(json_file_path)

    # BUILD SANDBOX DATA MAP WITH SANDBOX ID AS KEY
    # REMOVE ITEM FROM MAP WHEN SETUP FINISHES
    sb_map = {}
    for sb_data in sandbox_data_list:
        sb_map[sb_data.sandbox_id] = sb_data

    sandbox_count = len(sandbox_data_list)

    # STOP SANDBOXES
    logger.info("=== Stopping {} Sandboxes ===".format(sandbox_count))
    start = default_timer()
    for curr_sb_data in sandbox_data_list:
        try:
            sb_rest.stop_sandbox(curr_sb_data.sandbox_id)
        except Exception as e:
            exc_msg = "Can't end sandbox '{}'.Retrying. Exception {}".format(curr_sb_data.sandbox_id,
                                                                             str(e))
            logger.error(exc_msg)
            sleep(5)
            try:
                sb_rest.stop_sandbox(curr_sb_data.sandbox_id)
            except Exception as e:
                exc_msg = "Can't end sandbox '{}'. Raising Exception {}".format(curr_sb_data.sandbox_id,
                                                                                str(e))
                logger.exception(exc_msg)
                raise Exception(exc_msg)
        sleep(1)

    # LET TEARDOWN RUN A BIT
    logger.info("Waiting {} minutes before polling teardown...".format(run_config.estimated_teardown_minutes))
    sleep(run_config.estimated_teardown_minutes * 60)

    # POLL TEARDOWN
    finished_teardowns = []
    failed_teardowns = []
    total_polling_minutes = run_config.teardown_polling_timeout
    t_end = time() + (60 * total_polling_minutes)
    logger.info("Beginning polling for max of {} minutes".format(total_polling_minutes))
    while time() < t_end:
        for curr_sb_id in list(sb_map.keys()):
            sb_data = sb_map[curr_sb_id]
            try:
                sb_details = sb_rest.get_sandbox_data(curr_sb_id)
            except Exception as e:
                if "rate quota" in str(e):
                    logger.error("api rate quota exceeded. Waiting and re-polling...")
                    sleep(10)
                    sb_details = sb_rest.get_sandbox_data(curr_sb_id)
                else:
                    exc_msg = "Issue during polling: {}".format(str(e))
                    logger.exception(exc_msg)
                    raise (exc_msg)

            state = sb_details["state"]
            if state == my_globals.SANDBOX_ENDED_STATE:
                setup_errors = sb_data.setup_errors
                if setup_errors:
                    sleep(3)

                    # can search activity feed either by latest event id or "since" current timestamp
                    sorted_errors = sorted(setup_errors, key=lambda x: x["id"])
                    last_setup_error_id = sorted_errors.pop()["id"]
                    # curr_ts = get_utc_iso_8601_timestamp()
                    activity_feed_errors = sb_rest.get_sandbox_activity(sandbox_id=curr_sb_id,
                                                                        error_only=True,
                                                                        from_event_id=last_setup_error_id + 1)
                else:
                    sleep(3)
                    activity_feed_errors = sb_rest.get_sandbox_activity(sandbox_id=curr_sb_id,
                                                                        error_only=True)
                if activity_feed_errors:
                    failed_teardowns.append(curr_sb_id)
                    sb_data.teardown_errors = activity_feed_errors
                    logger.error("Failed teardown: {}".format(curr_sb_id))
                else:
                    logger.info("Completed Teardown: {}".format(curr_sb_id))
                finished_teardowns.append(sb_data)
                del sb_map[curr_sb_id]
            sleep(2)  # add some buffer to the api requests
        if not sb_map:
            break

        # POLLING DELAY
        sleep(run_config.polling_frequency_seconds)
    else:
        # POLLING TIMEOUT
        exc_msg = "Teardown Polling not completed within {} minutes".format(total_polling_minutes)
        logger.error(exc_msg)
        raise Exception(exc_msg)

    elapsed = int(default_timer() - start)
    elapsed = int(elapsed / 60)
    logger.info("Sandboxes Done Tearing Down. Elapsed: '{}' minutes".format(elapsed))

    with open(json_file_path, 'w') as f:
        sb_data_json = get_json_from_nested_obj(finished_teardowns)
        f.write(sb_data_json)

    logger.info("JSON data file written: '{}'".format(json_file_path))

    # VALIDATE RESULTS
    if failed_teardowns:
        failed_count = len(failed_teardowns)
        err_msg = "=== {} failed teardowns ===\n{}".format(failed_count, json.dumps(failed_teardowns, indent=4))
        logger.error(err_msg)
        raise Exception("{} Failed Teardowns!".format(failed_count))

    logger.info("Teardown flow done with no errors.")


if __name__ == "__main__":
    """
    When Triggering stop independently, latest timestamp is used, unless you provide override
    """
    try:
        api_config, run_config = get_config_data()
    except Exception as e:
        exc_msg = "Make sure config.json file is present. See ReadME for sample. Exception: {}".format(str(e))
        raise Exception(exc_msg)

    latest_json_time_stamp = _get_latest_json_log_timestamp(run_config.blueprint_id)
    log_path = build_log_path(latest_json_time_stamp, run_config.blueprint_id)
    logger = get_logger(log_path)
    try:
        sb_rest = SandboxRest(username=api_config.user,
                              password=api_config.password,
                              server=api_config.host,
                              port=api_config.port,
                              domain=api_config.domain,
                              logger=logger)
    except Exception as e:
        exc_msg = "Could not get sandbox rest session: {}".format(str(e))
        logger.exception(exc_msg)
        raise Exception(exc_msg)

    stop_sandboxes(sb_rest, run_config, latest_json_time_stamp, logger)
