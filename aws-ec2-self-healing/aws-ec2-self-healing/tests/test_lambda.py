import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# boto3 is bundled in Lambda; stub it so tests run anywhere without AWS.
sys.modules.setdefault("boto3", MagicMock())
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

import lambda_function as lf  # noqa: E402


def sns_event(state="ALARM", metric="procstat_lookup_pid_count", instance="i-0abc"):
    message = {
        "AlarmName": "self-healing-nginx-down",
        "NewStateValue": state,
        "NewStateReason": "threshold crossed",
        "Trigger": {
            "MetricName": metric,
            "Dimensions": [
                {"name": "InstanceId", "value": instance},
                {"name": "exe", "value": "nginx"},
            ],
        },
    }
    return {"Records": [{"Sns": {"Message": json.dumps(message)}}]}


class ParseTests(unittest.TestCase):
    def test_parse_alarm(self):
        parsed = lf.parse_alarm(sns_event())
        self.assertEqual(parsed["instance_id"], "i-0abc")
        self.assertEqual(parsed["state"], "ALARM")
        self.assertEqual(parsed["metric"], "procstat_lookup_pid_count")


class HandlerTests(unittest.TestCase):
    def test_ok_state_is_ignored(self):
        with patch.object(lf, "restart_nginx") as restart:
            result = lf.lambda_handler(sns_event(state="OK"), None)
        restart.assert_not_called()
        self.assertEqual(result["action"], "ignored")

    def test_nginx_alarm_restarts_and_notifies(self):
        with patch.object(lf, "restart_nginx", return_value=(True, "Success", "ok")) as restart, \
             patch.object(lf, "notify_slack") as slack:
            result = lf.lambda_handler(sns_event(), None)
        restart.assert_called_once_with("i-0abc")
        self.assertTrue(result["success"])
        self.assertTrue(slack.call_args[0][0])

    def test_status_check_alarm_reboots(self):
        event = sns_event(metric="StatusCheckFailed_Instance")
        with patch.object(lf, "reboot_instance", return_value=(True, "RebootRequested", "")) as reboot, \
             patch.object(lf, "notify_slack"):
            lf.lambda_handler(event, None)
        reboot.assert_called_once_with("i-0abc")

    def test_failure_is_reported(self):
        with patch.object(lf, "restart_nginx", side_effect=RuntimeError("boom")), \
             patch.object(lf, "notify_slack") as slack:
            result = lf.lambda_handler(sns_event(), None)
        self.assertFalse(result["success"])
        self.assertFalse(slack.call_args[0][0])

    def test_missing_instance_id(self):
        event = sns_event()
        msg = json.loads(event["Records"][0]["Sns"]["Message"])
        msg["Trigger"]["Dimensions"] = []
        event["Records"][0]["Sns"]["Message"] = json.dumps(msg)
        with patch.object(lf, "notify_slack"):
            result = lf.lambda_handler(event, None)
        self.assertEqual(result["action"], "failed")


class SlackTests(unittest.TestCase):
    def test_skips_when_not_configured(self):
        with patch.object(lf, "_slack_webhook", return_value="not-configured"), \
             patch("urllib.request.urlopen") as urlopen:
            lf.notify_slack(True, "t", {"a": "b"})
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
