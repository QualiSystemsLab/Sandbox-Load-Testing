"""
Sandbox API can be explored further at <sandbox_api_server>:82/api/v2/explore
"""

import requests  # pip install requests
import json


class SandboxRest(object):
    def __init__(self, server, username, password, domain="Global", token="", port="82", api_version="v2", logger=None):
        """
        run login command on init, attach session token to headers for subsequent requests
        :param str server:
        :param str username:
        :param str password:
        :param str domain:
        :param str api_version:
        :param logging.Logger logger:
        """
        self._base_url = "http://{server}:{port}/api/{api_version}".format(server=server,
                                                                           port=port,
                                                                           api_version=api_version)
        self._auth_headers = self._get_auth_headers(server, username, password, domain)
        self._logger = logger

    @staticmethod
    def _get_auth_headers(server, user_name, password, domain):
        """
        Get token from login response, then place token into auth headers on class
        """
        login_data = {
            "username": user_name,
            "password": password,
            "domain": domain
        }
        login_url = "http://{server}:82/api/login".format(server=server)
        login_headers = {"Content-Type": "application/json"}
        login_res = requests.put(url=login_url,
                                 data=json.dumps(login_data),
                                 headers=login_headers)
        if login_res.status_code in [200, 202]:
            login_token = login_res.text[1:-1]
        else:
            print("login response code: " + str(login_res.status_code))
            print("login response" + login_res.text)
            raise Exception("Sandbox API authentication Failed")

        auth_headers = {
            'Authorization': 'Basic {0}'.format(login_token),
            'Content-Type': 'application/json'
        }
        return auth_headers

    @staticmethod
    def _handle_res_json(response):
        """
        gets api response, checks status code, if passed returns json, else raises Exception
        :param response:
        :return:
        """
        if 200 <= response.status_code < 300:
            return response.json()
        else:
            raise Exception(
                "Failed Sandbox API request: code '{}', {}".format(str(response.status_code), response.text))

    def _log(self, message):
        """
        validate that logger exists and log
        :param str message:
        :return:
        """
        if self._logger:
            self._logger.info(message)

    def start_blueprint(self, blueprint_id, sandbox_name="Rest Api Sandbox", duration="PT0H20M", params=None):
        """
        start sandbox from blueprint, will return sandbox info with "id", "blueprint_id", sandbox components list etc.
        view docs for full response structure
        :param str blueprint_id:
        :param str sandbox_name:
        :param str duration: Duration format must be a valid 'ISO 8601'. (e.g 'PT23H' or 'PT4H2M')
        :param list params: should be list of [{"name": "value"}] dicts
        :return:
        """
        request_url = self._base_url + "/blueprints/{blueprint_id}/start".format(blueprint_id=blueprint_id)
        params = params if params else []
        body = {
            "name": sandbox_name,
            "duration": duration,
            "params": params
        }
        response = requests.post(url=request_url, data=json.dumps(body), headers=self._auth_headers)
        return self._handle_res_json(response)

    def stop_sandbox(self, sandbox_id):
        """
        stop current sandbox
        :param str sandbox_id:
        :return:
        """
        request_url = self._base_url + "/sandboxes/{sandbox_id}/stop".format(sandbox_id=sandbox_id)
        response = requests.post(url=request_url, headers=self._auth_headers)
        return self._handle_res_json(response)

    def get_sandbox_data(self, sandbox_id):
        """
        get sandbox info. "id", "blueprint_id" etc.
        "setup_stage" value is very useful for polling when the sandbox is ready
        :param str sandbox_id:
        :return:
        """
        request_url = self._base_url + "/sandboxes/{sandbox_id}".format(sandbox_id=sandbox_id)

        response = requests.get(url=request_url, headers=self._auth_headers)
        return self._handle_res_json(response)

    def get_sandbox_components(self, sandbox_id):
        """
        get sandbox info. "id", "blueprint_id" etc.
        "setup_stage" value is very useful for polling when the sandbox is ready
        :param str sandbox_id:
        :return:
        """
        request_url = self._base_url + "/sandboxes/{sandbox_id}/components".format(sandbox_id=sandbox_id)
        response = requests.get(url=request_url, headers=self._auth_headers)
        return self._handle_res_json(response)

    def start_component_command(self, sandbox_id, component_id, command_name, params=[], print_output=False):
        """
        start command of component in sandbox. returns json with "executionId", "supports_cancellation" keys
        :param str sandbox_id:
        :param str component_id:
        :param str command_name:
        :param [] params: a list of command arguments in the form [{"name":"string", "value":"string"}, {...}]
        :param bool print_output:
        :return:
        """
        body = {
            "params": params,
            "printOutput": print_output
        }

        start_url = self._base_url + '/sandboxes/{sandbox_id}/components/{component_id}/commands/{command_name}/start'.format(
            sandbox_id=sandbox_id,
            component_id=component_id,
            command_name=command_name)

        response = requests.post(url=start_url, data=json.dumps(body), headers=self._auth_headers)
        return self._handle_res_json(response)

    def get_execution_data(self, execution_id):
        """
        returns json with keys "id", "status", "supports_cancellation", "started", "ended", "output"
        :param str execution_id:
        :return:
        """
        execution_url = self._base_url + '/executions/{execution_id}'.format(execution_id=execution_id)

        response = requests.get(url=execution_url, headers=self._auth_headers)
        return self._handle_res_json(response)

    def get_sandbox_activity(self, sandbox_id, error_only=False, since="", from_event_id="", tail=""):
        """
        get the activity feed data in json format. Example response:
        {
          "num_returned_events": 500,
          "more_pages": "true",
          "next_event_id": 9129,
          "events": [
            {
              "id": 9128,
              "event_type": "success",
              "event_text": "Sandbox 'Sandbox-4-18-20...' has started",
              "output": "Driver SD-78 failed to establish connection!",
              "time": "2019-10-07T14:50:53.503Z"
            }
          ]
        }
        :param sandbox_id:
        :param bool error_only:
        :param str since: Events starting time in "ISO 8601" Standard. (e.g '2000-12-31T23:59:60Z')
        :param str from_event_id: Entry id of first output entry to return
        :param str tail: Get last X events
        :return:
        """
        activity_url = self._base_url + '/sandboxes/{}/activity'.format(sandbox_id)

        # append query params
        error_only = "true" if error_only else "false"
        activity_url += "?error_only={}".format(error_only)

        if since:
            activity_url += "&since={}".format(since)

        if from_event_id:
            activity_url += "&from_event_id={}".format(from_event_id)

        if tail:
            activity_url += "&tail={}".format(tail)

        if self._logger:
            self._logger.debug("sending url: {}".format(activity_url))

        response = requests.get(url=activity_url, headers=self._auth_headers)
        data = self._handle_res_json(response)
        events = data["events"]
        return events

    def get_sandboxes(self, show_historic=False):
        # historic sandboxes are completed sandboxes
        show_historic = "true" if show_historic else "false"

        url = self._base_url + "/sandboxes" + "?show_historic={}".format(show_historic)
        response = requests.get(url=url, headers=self._auth_headers)
        data = self._handle_res_json(response)
        return data

    def get_console_output(self, sandbox_id: str, tail=0):
        """
        get console entries from sandbox
        get back list of entries. list of dicts
        [{"id":"asdf", "time": "12:00", "text": "bla, bla, bla"}, ...]
        """
        url = f"{self._base_url}/sandboxes/{sandbox_id}/output"

        # append query param if set
        if tail:
            url += f"?tail={tail}"

        response = requests.get(url=url, headers=self._auth_headers)
        data = self._handle_res_json(response)
        entries = data.get("entries")
        if not entries:
            raise Exception("API Response has no 'entries'. Response: ".format(data))
        return entries


if __name__ == "__main__":
    server = "localhost"
    cs_user = "admin"
    password = "admin"
    domain = "Global"
    SANDBOX_ID = "2b3c062b-f274-492d-b6d0-276c2d49a546"

    sb_rest = SandboxRest("localhost", "admin", "admin")
    entries = sb_rest.get_console_output(SANDBOX_ID)
    sandbox_info = sb_rest.get_sandboxes()
    info_json = json.dumps(sandbox_info, indent=2)
    print(info_json)
    pass
