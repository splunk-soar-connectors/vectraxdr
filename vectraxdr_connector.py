# File: vectraxdr_connector.py
#
# Copyright (c) Vectra, 2023-2026
#
# This unpublished material is proprietary to Vectra.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Vectra.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

import json

import phantom.app as phantom
import requests
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

import vectraxdr_consts as consts
from actions.vectraxdr_add_assignment import AddAssignmentAction
from actions.vectraxdr_add_note import AddNoteAction
from actions.vectraxdr_add_tags import AddTagsAction
from actions.vectraxdr_describe_detection import DescribeDetectionAction
from actions.vectraxdr_describe_entity import DescribeEntityAction
from actions.vectraxdr_download_pcap import DownloadPCAPAction
from actions.vectraxdr_list_entity_detections import ListEntityDetectionsAction
from actions.vectraxdr_mark_detection import MarkDetectionAction
from actions.vectraxdr_mark_entity_detections import MarkEntityDetectionsAction
from actions.vectraxdr_on_poll import OnPollAction
from actions.vectraxdr_remove_note import RemoveNoteAction
from actions.vectraxdr_remove_tags import RemoveTagsAction
from actions.vectraxdr_resolve_assignment import ResolveAssignmentAction
from actions.vectraxdr_test_connectivity import TestConnectivityAction
from actions.vectraxdr_unmark_detection import UnmarkDetectionAction
from actions.vectraxdr_update_assignment import UpdateAssignmentAction
from actions.vectraxdr_update_note import UpdateNoteAction
from vectraxdr_utils import VectraxdrUtils


ACTION_HANDLERS = {
    "add_assignment": AddAssignmentAction,
    "add_note": AddNoteAction,
    "add_tags": AddTagsAction,
    "describe_detection": DescribeDetectionAction,
    "describe_entity": DescribeEntityAction,
    "download_pcap": DownloadPCAPAction,
    "list_entity_detections": ListEntityDetectionsAction,
    "mark_detection": MarkDetectionAction,
    "mark_entity_detections": MarkEntityDetectionsAction,
    "on_poll": OnPollAction,
    "remove_note": RemoveNoteAction,
    "remove_tags": RemoveTagsAction,
    "resolve_assignment": ResolveAssignmentAction,
    "test_connectivity": TestConnectivityAction,
    "unmark_detection": UnmarkDetectionAction,
    "update_assignment": UpdateAssignmentAction,
    "update_note": UpdateNoteAction,
}


class VectraxdrConnector(BaseConnector):
    """Vectra xdr Connector class to interact with service API."""

    def __init__(self):
        """Prepare constructor for Vectra xdr."""
        super().__init__()

        self.state = None
        self.util = None
        self.config = None
        self._dup_entities = 0

    def handle_action(self, param):
        """Handle the flow of execution, calls the appropriate method for the action."""
        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()
        self.debug_print("action_id", self.get_action_identifier())

        action_class = ACTION_HANDLERS.get(action_id)
        if action_class:
            action = action_class(self, param)
            return action.execute()

        self.debug_print("Action not implemented")
        return phantom.APP_ERROR

    def initialize(self):
        """Set up method for the connector."""
        self.state = self.load_state()
        if not self.state or not isinstance(self.state, dict):
            self.state = {"app_version": self.get_app_json().get("app_version")}

        self.config = self.get_config()

        # Create the util object and use it throughout the action lifecycle
        self.util = VectraxdrUtils(self)
        client_id_of_state = self.state.get(consts.VECTRA_STATE_CLIENT_ID)
        client_id_of_config = self.config.get(consts.VECTRA_STATE_CLIENT_ID)

        if client_id_of_state is None:
            self.state[consts.VECTRA_STATE_CLIENT_ID] = client_id_of_config
        elif client_id_of_state != client_id_of_config:
            ret_val = self.util._generate_refresh_token(ActionResult({}))
            if phantom.is_fail(ret_val):
                self.state = {"app_version": self.get_app_json().get("app_version")}
                return self.set_status(phantom.APP_ERROR, "Unable to generate tokens")
            self.state[consts.VECTRA_STATE_CLIENT_ID] = client_id_of_config

        return phantom.APP_SUCCESS

    def finalize(self):
        """Tear down method for the connector."""
        self.state = self.util._encrypt_state(self.state)
        self.save_state(self.state)
        return phantom.APP_SUCCESS


def main():
    """Use this method to debug connector."""
    import argparse
    import sys

    argparser = argparse.ArgumentParser()

    argparser.add_argument("input_test_json", help="Input Test JSON file")
    argparser.add_argument("-u", "--username", help="username", required=False)
    argparser.add_argument("-p", "--password", help="password", required=False)
    argparser.add_argument("-v", "--verify", help="verify", required=False, default=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password
    verify = args.verify

    if username is not None and password is None:
        # User specified a username but not a password, so ask
        import getpass

        password = getpass.getpass("Password: ")

    if username and password:
        try:
            login_url = VectraxdrConnector._get_phantom_base_url() + "/login"

            print("Accessing the Login page")
            r = requests.get(login_url, verify=verify)
            csrftoken = r.cookies["csrftoken"]

            data = dict()
            data["username"] = username
            data["password"] = password
            data["csrfmiddlewaretoken"] = csrftoken

            headers = dict()
            headers["Cookie"] = "csrftoken=" + csrftoken
            headers["Referer"] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=verify, data=data, headers=headers)
            session_id = r2.cookies["sessionid"]
        except Exception as e:
            print("Unable to get session id from the platform. Error: " + str(e))
            sys.exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = VectraxdrConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json["user_session_token"] = session_id
            connector._set_csrf_info(csrftoken, headers["Referer"])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    sys.exit(0)


if __name__ == "__main__":
    main()
