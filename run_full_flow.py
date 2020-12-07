import os
from common import get_config_data, get_utc_timestamp
from run_start_sandboxes import start_sandboxes
from run_stop_sandboxes import stop_sandboxes
from time import sleep
from logger import get_logger
from sb_rest.sandbox_rest_api import SandboxRest
import my_globals
from pathlib import Path


def run_full_flow():
    try:
        api_config, run_config = get_config_data()
    except Exception as e:
        exc_msg = "Make sure config.json file is present. See ReadME for sample. Exception: {}".format(str(e))
        raise Exception(exc_msg)

    blueprint_name = run_config.blueprint_id
    time_stamp = get_utc_timestamp()
    current_dir = os.getcwd()
    logs_folder_path = os.path.join(current_dir, my_globals.LOGS_FOLDER, run_config.blueprint_id)

    # CREATE LOG FOLDER
    Path(logs_folder_path).mkdir(exist_ok=True, parents=True)
    log_name = "{}_{}.log".format(time_stamp, blueprint_name)
    log_file_path = os.path.join(logs_folder_path, log_name)
    logger = get_logger(log_file_path)
    
    logger.info("Starting FULL Flow")

    # GET API SESSION
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

    # START SANDBOXES
    try:
        start_sandboxes(sb_rest, run_config, time_stamp, logger)
    except Exception as e:
        logger.error("Errors during setup Flow!")
        # TODO - A failed setup will throw exception, define specific exception for this scenario to "pass"
        pass

    # LET SANDBOX BE ACTIVE FOR A BIT
    active_sandbox_minutes = run_config.active_sandbox_minutes
    logger.info("Sleeping {} minutes before teardown".format(active_sandbox_minutes))
    sleep(active_sandbox_minutes * 60)

    # END SANDBOXES
    try:
        stop_sandboxes(sb_rest, run_config, time_stamp, logger)
    except Exception as e:
        exc_msg = "Error during teardown flow: {}".format(str(e))
        logger.exception(exc_msg)
        raise Exception(exc_msg)


if __name__ == "__main__":
    run_full_flow()
