"""
Helper functions to poll the state of sandbox setup or the execution status of a command.
Leverages the python 'retrying' library to do polling:
https://pypi.org/project/retrying/
"""
from retrying import retry  # pip install retrying
from sb_rest.sandbox_rest_api import SandboxRest


def setup_state_validation(sandbox_state):
    if sandbox_state == "Ready":
        return False
    elif sandbox_state == "Ended":
        return False
    elif sandbox_state == "Error":
        return False
    else:
        return True


def execution_status_validation(exc_data):
    exc_status = exc_data["status"]
    exc_id = exc_data["id"]
    if exc_status == "Completed":
        return False
    elif exc_status == "Failed":
        raise Exception("sandbox command FAILED. check sandbox logs for more details.")
    else:
        return True


def poll_sandbox_state(sandbox_rest, reservation_id, max_polling_in_minutes=20, polling_frequency_in_seconds=30):
    """
    for polling sandbox during setup/teardown, can set max polling time and frequency of polling requests
    :param SandboxRest sandbox_rest:
    :param str reservation_id:
    :param int max_polling_in_minutes:
    :param int polling_frequency_in_seconds:
    :return:
    """
    # retry wait times are in milliseconds
    @retry(retry_on_result=setup_state_validation, wait_fixed=polling_frequency_in_seconds * 1000,
           stop_max_delay=max_polling_in_minutes * 60000)
    def get_sandbox_state(sb_rest, res_id):
        sandbox_data = sb_rest.get_sandbox_data(res_id)
        sandbox_state = sandbox_data["state"]
        return sandbox_state
    get_sandbox_state(sandbox_rest, reservation_id)


def get_execution_data_upon_completion(sandbox_rest, command_execution_id, max_polling_in_minutes=20,
                                       polling_frequency_in_seconds=30):
    """
    poll execution for "Completed" status, then return the execution data
    :param SandboxRest sandbox_rest:
    :param str command_execution_id:
    :param int max_polling_in_minutes:
    :param int polling_frequency_in_seconds:
    :return:
    """
    # retry wait times are in milliseconds
    @retry(retry_on_result=execution_status_validation, wait_fixed=polling_frequency_in_seconds * 1000,
           stop_max_delay=max_polling_in_minutes * 60000)
    def get_execution_data(sb_rest, execution_id):
        exc_data = sb_rest.get_execution_data(execution_id)
        return exc_data
    execution_data = get_execution_data(sandbox_rest, command_execution_id)
    return execution_data
