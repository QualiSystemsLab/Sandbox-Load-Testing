from sb_rest.sandbox_rest_api import SandboxRest
from timeit import default_timer
from time import time, sleep
import json
from common import SandboxErrorData, get_config_data, get_utc_timestamp, sandbox_name_truncater, \
    get_json_from_nested_obj, RunConfig
from logger import get_logger
import my_globals
import os
from pathlib import Path


def start_sandboxes(sb_rest, run_config, time_stamp, logger):
    """

    :param SandboxRest sb_rest:
    :param RunConfig run_config:
    :param str time_stamp: appended to json-results file and sandbox name
    :param logging.Logger logger:
    :return:
    """

    sandbox_name = "{} - {}".format(time_stamp, run_config.blueprint_id)
    sandbox_name = sandbox_name_truncater(sandbox_name)

    # START SANDBOXES
    logger.info("=== Starting {} sandboxes ===".format(run_config.sandbox_quantity))
    start = default_timer()
    started_sandboxes = []
    for i in range(run_config.sandbox_quantity):
        sb_details = sb_rest.start_blueprint(blueprint_id=run_config.blueprint_id,
                                             sandbox_name=sandbox_name,
                                             duration=run_config.sandbox_duration,
                                             params=run_config.blueprint_params)
        sb_id = sb_details["id"]
        sb_data = SandboxErrorData(sb_id)
        started_sandboxes.append(sb_data)

    # LET SETUP RUN A BIT
    logger.info("Waiting {} minutes before polling setup...".format(run_config.initial_timeout_minutes))
    sleep(run_config.initial_timeout_minutes * 60)

    # BUILD SANDBOX DATA MAP WITH ID AS KEY
    # REMOVE ITEM FROM MAP WHEN SETUP FINISHES
    sb_map = {}
    for sb_data in started_sandboxes:
        sb_map[sb_data.sandbox_id] = sb_data

    # POLL THE SETUP
    finished_setups = []
    failed_setups = []
    total_polling_minutes = run_config.orch_polling_minutes
    t_end = time() + (60 * total_polling_minutes)
    while time() < t_end:
        for sb_id, sb_data in list(sb_map.items()):
            sb_details = sb_rest.get_sandbox_data(sb_id)
            state = sb_details["state"]
            if state == my_globals.SANDBOX_ERROR_STATE:
                sb_data.failed_setup_stage = sb_details["setup_stage"]
                activity_feed_errors = sb_rest.get_sandbox_activity(sb_id, True)
                sb_data.setup_errors = activity_feed_errors
                finished_setups.append(sb_data)
                failed_setups.append(sb_id)
                del sb_map[sb_id]
                logger.error("Failed setup: {}, stage: {}".format(sb_id, sb_data.failed_setup_stage))
                continue
            if state == my_globals.SANDBOX_READY_STATE:
                logger.info("Sandbox {} Active".format(sb_id))
                finished_setups.append(sb_data)
                del sb_map[sb_id]
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
    logger.info("Sandboxes Done. Elapsed: '{}' seconds".format(elapsed))

    # STORE SETUP DATA TO JSON FILE
    current_dir = os.getcwd()
    log_folder_path = os.path.join(current_dir, my_globals.JSON_RESULTS_FOLDER, run_config.blueprint_id)
    Path(log_folder_path).mkdir(exist_ok=True, parents=True)  # make folder if it doesn't exist

    json_file_name = "{}_{}.json".format(time_stamp, run_config.blueprint_id)
    json_file_path = os.path.join(log_folder_path, json_file_name)
    with open(json_file_path, 'w') as f:
        sb_data_json = get_json_from_nested_obj(finished_setups)
        f.write(sb_data_json)

    logger.info("JSON data file written: '{}'".format(json_file_path))

    # VALIDATE RESULTS
    if failed_setups:
        failed_count = len(failed_setups)
        err_msg = "=== {} failed setups ===\n{}".format(failed_count, json.dumps(failed_setups, indent=4))
        logger.error(err_msg)
        raise Exception("{} Failed Setups!".format(failed_count))

    logger.info("Setup flow done with no errors")


if __name__ == "__main__":
    try:
        api_config, run_config = get_config_data()
    except Exception as e:
        exc_msg = "Make sure config.json file is present. See ReadME for sample. Exception: {}".format(str(e))
        raise Exception(exc_msg)

    blueprint_name = run_config.blueprint_id
    time_stamp = get_utc_timestamp()

    current_dir = os.getcwd()
    logs_folder_path = os.path.join(current_dir, my_globals.LOGS_FOLDER, run_config.blueprint_id)
    Path(logs_folder_path).mkdir(exist_ok=True, parents=True)

    log_file_name = "{}_{}.log".format(time_stamp, blueprint_name)
    log_file_path = os.path.join(logs_folder_path, log_file_name)
    logger = get_logger(log_file_path)

    try:
        sb_rest = SandboxRest(username=api_config.user,
                              password=api_config.password,
                              server=api_config.host,
                              port=api_config.port,
                              domain=api_config.domain)
    except Exception as e:
        exc_msg = "Could not get sandbox rest session: {}".format(str(e))
        logger.exception(exc_msg)
        raise Exception(exc_msg)
    start_sandboxes(sb_rest, run_config, time_stamp, logger)
