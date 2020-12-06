from sb_rest.sandbox_rest_api import SandboxRest
from sb_rest.common import get_utc_iso_8601_timestamp
from timeit import default_timer
from time import time, sleep
import json
from common import SandboxErrorData, get_config_data, get_json_from_nested_obj, RunConfig
from logger import get_logger
import my_globals
import os
from datetime import datetime


def get_latest_json_log_path(blueprint_id):
    """
    find latest dated log in blueprint json results folder
    sample results file name - 05-12-20_221829_<blueprint_name>.json
    :param str blueprint_id: refers to folder inside json-results
    :return:
    """
    current_dir = os.getcwd()
    sandbox_dir_path = os.path.join(current_dir, my_globals.JSON_RESULTS_FOLDER, blueprint_id)
    json_files = os.listdir(sandbox_dir_path)
    time_stamp_strings = ["_".join(x.split("_")[:-1]) for x in json_files]
    datetime_time_stamps = [datetime.strptime(ts, my_globals.TIMESTAMP_FORMATTING) for ts in time_stamp_strings]
    datetime_time_stamps.sort()
    latest_timestamp = datetime_time_stamps.pop()
    latest_timestamp_str = datetime.strftime(latest_timestamp, my_globals.TIMESTAMP_FORMATTING)
    json_file_name = "{}_{}.json".format(latest_timestamp_str, blueprint_id)
    json_full_path = os.path.join(sandbox_dir_path, json_file_name)
    return json_full_path


def get_latest_log_path(blueprint_id):
    """
    find latest dated log file in logs folder
    sample file name - 05-12-20_221829_<blueprint_name>.log
    :param str blueprint_id: refers to folder inside json-results
    :return:
    """
    current_dir = os.getcwd()
    log_dir_path = os.path.join(current_dir, my_globals.LOGS_FOLDER)
    file_names = os.listdir(log_dir_path)
    time_stamp_strings = ["_".join(x.split("_")[:-1]) for x in file_names]
    datetime_time_stamps = [datetime.strptime(ts, my_globals.TIMESTAMP_FORMATTING) for ts in time_stamp_strings]
    datetime_time_stamps.sort()
    latest_timestamp = datetime_time_stamps.pop()
    latest_timestamp_str = datetime.strftime(latest_timestamp, my_globals.TIMESTAMP_FORMATTING)
    log_file_name = "{}_{}.log".format(latest_timestamp_str, blueprint_id)
    log_file_full_path = os.path.join(log_dir_path, log_file_name)
    return log_file_full_path


def _get_sandbox_data_from_json(path):
    with open(path) as config_file:
        data = json.load(config_file)
    obj_wrapped_data = [SandboxErrorData(sandbox_id=x["sandbox_id"],
                                         failed_setup_stage=x["failed_setup_stage"],
                                         setup_errors=x["setup_errors"])
                        for x in data]
    return obj_wrapped_data


def stop_sandboxes(sb_rest, run_config, logger):
    """

    :param SandboxRest sb_rest:
    :param RunConfig run_config:
    :param logging.Logger logger:
    :return:
    """
    latest_json_log_path = get_latest_json_log_path(run_config.blueprint_id)
    sandbox_data_list = _get_sandbox_data_from_json(latest_json_log_path)

    # BUILD SANDBOX DATA MAP WITH ID AS KEY
    # REMOVE ITEM FROM MAP WHEN SETUP FINISHES
    sb_map = {}
    for sb_data in sandbox_data_list:
        sb_map[sb_data.sandbox_id] = sb_data

    sandbox_count = len(sandbox_data_list)

    # STOP SANDBOXES
    logger.info("Stopping {} Sandboxes...".format(sandbox_count))
    start = default_timer()
    for curr_sb_data in sandbox_data_list:
        try:
            sb_rest.stop_sandbox(curr_sb_data.sandbox_id)
        except Exception as e:
            exc_msg = "Can't end sandbox '{}'. Perhaps it is already completed: {}".format(curr_sb_data.sandbox_id,
                                                                                           str(e))
            logger.info(exc_msg)

    # POLL TEARDOWN
    finished_teardowns = []
    failed_teardowns = []
    t_end = time() + (60 * run_config.orch_polling_minutes)
    while time() < t_end:
        for curr_sb_id in list(sb_map.keys()):
            sb_data = sb_map[curr_sb_id]
            sb_details = sb_rest.get_sandbox_data(curr_sb_id)
            state = sb_details["state"]
            if state == my_globals.SANDBOX_ENDED_STATE:
                setup_errors = sb_data.setup_errors
                if setup_errors:
                    sorted_errors = sorted(setup_errors, key=lambda x: x["id"])
                    last_setup_error_id = sorted_errors.pop()["id"]
                    # curr_ts = get_utc_iso_8601_timestamp()
                    activity_feed_errors = sb_rest.get_sandbox_activity(sandbox_id=curr_sb_id,
                                                                        error_only=True,
                                                                        from_event_id=last_setup_error_id + 1)
                else:
                    activity_feed_errors = sb_rest.get_sandbox_activity(sandbox_id=curr_sb_id,
                                                                        error_only=True)
                if activity_feed_errors:
                    failed_teardowns.append(curr_sb_id)
                    sb_data.teardown_errors = activity_feed_errors
                    logger.error("Failed teardown: {}".format(curr_sb_id))
                finished_teardowns.append(sb_data)
                del sb_map[curr_sb_id]
        if not sb_map:
            break
        # POLLING DELAY
        sleep(run_config.polling_frequency_seconds)

    elapsed = int(default_timer() - start)
    logger.info("Sandboxes Done Tearing Down. Elapsed: '{}' seconds".format(elapsed))

    with open(latest_json_log_path, 'w') as f:
        sb_data_json = get_json_from_nested_obj(finished_teardowns)
        f.write(sb_data_json)

    logger.info("JSON data file written: '{}'".format(latest_json_log_path))

    # VALIDATE RESULTS
    if failed_teardowns:
        failed_count = len(failed_teardowns)
        err_msg = "=== {} failed teardowns ===\n{}".format(failed_count, json.dumps(failed_teardowns, indent=4))
        logger.error(err_msg)
        raise Exception("{} Failed Teardowns!".format(failed_count))

    logger.info("Teardown flow done with no errors.")


if __name__ == "__main__":
    try:
        api_config, run_config = get_config_data()
    except Exception as e:
        exc_msg = "Make sure config.json file is present. See ReadME for sample. Exception: {}".format(str(e))
        raise Exception(exc_msg)
    latest_log_path = get_latest_log_path(run_config.blueprint_id)
    logger = get_logger(latest_log_path)
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

    stop_sandboxes(sb_rest, run_config, logger)
