import json
import os
import typing
from collections import OrderedDict
from datetime import datetime

from my_globals import TIMESTAMP_FORMATTING

CONFIG_FILE_NAME = "config.json"


class ApiConfig(typing.NamedTuple):
    host: str
    port: int
    user: str
    password: str
    domain: str


class RunConfig(typing.NamedTuple):
    blueprint_id: str
    sandbox_quantity: int
    sandbox_duration_iso_formatted: str
    active_sandbox_minutes: int
    blueprint_params: dict
    setup_polling_timeout: int
    teardown_polling_timeout: int
    estimated_setup_minutes: int
    estimated_teardown_minutes: int
    polling_frequency_seconds: int


class ActiveWithErrorException(Exception):
    """ If a polled child sandbox is active with error """
    pass


def get_utc_timestamp():
    return datetime.utcnow().strftime(TIMESTAMP_FORMATTING)


def _get_iso_formatted_time_from_minutes(minutes):
    """
    take input minutes and format to proper format for Request
    :param int minutes:
    :return:
    """
    if minutes > 60:
        hours = int(minutes / 60)
        minutes = minutes % 60
        return "PT{}H{}M".format(hours, minutes)
    return "PT0H{}M".format(minutes)


def get_config_data() -> typing.Tuple[ApiConfig, RunConfig]:
    """
    read json file return tuple of config data objects
    :return:
    """
    current_dir = os.getcwd()
    config_full_path = os.path.join(current_dir, CONFIG_FILE_NAME)
    with open(config_full_path) as config_file:
        data = json.load(config_file)

    api_data = data["api_data"]
    run_data = data["run_config"]

    api_config = ApiConfig(host=api_data["sandbox_rest_server"],
                           port=api_data["port"],
                           user=api_data["user"],
                           password=api_data["password"],
                           domain=api_data["domain"])

    sandbox_duration_minutes = run_data["sandbox_duration_minutes"]
    sandbox_duration_iso_formatted = _get_iso_formatted_time_from_minutes(sandbox_duration_minutes)
    run_config = RunConfig(blueprint_id=run_data["blueprint_id"],
                           sandbox_quantity=run_data["sandbox_quantity"],
                           sandbox_duration_iso_formatted=sandbox_duration_iso_formatted,
                           active_sandbox_minutes=run_data["active_sandbox_minutes"],
                           setup_polling_timeout=run_data["setup_polling_timeout"],
                           teardown_polling_timeout=run_data["teardown_polling_timeout"],
                           blueprint_params=run_data["blueprint_params"],
                           estimated_setup_minutes=run_data["estimated_setup_minutes"],
                           estimated_teardown_minutes=run_data["estimated_teardown_minutes"],
                           polling_frequency_seconds=run_data["polling_frequency_seconds"])
    return api_config, run_config


class SandboxErrorData(object):
    def __init__(self, sandbox_id, failed_setup_stage=None, setup_errors=None, teardown_errors=None):
        """
        To gather error data from sandboxes during orchestration
        :param str sandbox_id:
        """
        self.sandbox_id = sandbox_id
        self.failed_setup_stage = failed_setup_stage if failed_setup_stage else None
        self.setup_errors = setup_errors if setup_errors else None
        self.teardown_errors = teardown_errors if teardown_errors else None

    def get_ordered_json(self):
        """
        order the dict before returning JSON - to keep report output consistent
        :return:
        """
        my_dict = OrderedDict()
        my_dict["sandbox_id"] = self.sandbox_id
        my_dict["failed_setup_stage"] = self.failed_setup_stage
        my_dict["setup_errors"] = self.setup_errors
        my_dict["teardown_errors"] = self.teardown_errors
        return json.dumps(my_dict, indent=4)


def sandbox_name_truncater(input_str: str):
    """ keep sandbox name under 60 chars """
    sandbox_max_characters = 60
    max_minus_ellipses = sandbox_max_characters - 2
    if len(input_str) > sandbox_max_characters:
        return input_str[:max_minus_ellipses] + '..'
    else:
        return input_str


def get_json_from_nested_obj(obj):
    return json.dumps(obj, default=lambda o: getattr(o, '__dict__', str(o)), indent=4)
