"""
Self-healing Lambda.

Triggered by SNS (which receives CloudWatch alarm state changes).

  * NGINX process alarm  -> run the SSM document that restarts NGINX
  * EC2 status-check alarm -> reboot the instance

Every outcome (success or failure) is reported to Slack.
Only the standard library and boto3 (bundled in the Lambda runtime) are used.
"""
import json
import logging
import os
import time
import urllib.request

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SSM_DOCUMENT_NAME = os.environ.get("SSM_DOCUMENT_NAME", "")
SLACK_WEBHOOK_PARAM = os.environ.get("SLACK_WEBHOOK_PARAM", "")
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("COMMAND_TIMEOUT_SECONDS", "90"))

ssm = boto3.client("ssm")
ec2 = boto3.client("ec2")

_webhook_cache = None
TERMINAL_STATES = {"Success", "Failed", "TimedOut", "Cancelled"}


# ----------------------------------------------------------------- parsing
def parse_alarm(event):
    """Extract the useful fields from an SNS-wrapped CloudWatch alarm."""
    sns = event["Records"][0]["Sns"]
    message = json.loads(sns["Message"])
    trigger = message.get("Trigger", {})
    dimensions = {d["name"]: d["value"] for d in trigger.get("Dimensions", [])}
    return {
        "alarm_name": message.get("AlarmName", "unknown"),
        "state": message.get("NewStateValue", "UNKNOWN"),
        "reason": message.get("NewStateReason", ""),
        "metric": trigger.get("MetricName", ""),
        "instance_id": dimensions.get("InstanceId"),
    }


# ------------------------------------------------------------------ Slack
def _slack_webhook():
    global _webhook_cache
    if _webhook_cache is None:
        _webhook_cache = ""
        if SLACK_WEBHOOK_PARAM:
            try:
                resp = ssm.get_parameter(Name=SLACK_WEBHOOK_PARAM, WithDecryption=True)
                _webhook_cache = resp["Parameter"]["Value"]
            except Exception:  # noqa: BLE001
                logger.exception("Could not read Slack webhook parameter")
    return _webhook_cache


def notify_slack(ok, title, details):
    """Post a message to Slack. Never raises - notification must not break healing."""
    webhook = _slack_webhook()
    if not webhook.startswith("https://"):
        logger.info("Slack webhook not configured, skipping notification")
        return
    icon = ":white_check_mark:" if ok else ":rotating_light:"
    body = {
        "text": f"{icon} {title}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{icon} {title}"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{k}:*\n{v}"} for k, v in details.items()
                ],
            },
        ],
    }
    req = urllib.request.Request(
        webhook,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            logger.info("Slack responded %s", resp.status)
    except Exception:  # noqa: BLE001
        logger.exception("Slack notification failed")


# ---------------------------------------------------------------- healing
def restart_nginx(instance_id):
    """Run the SSM document and wait for it. Returns (success, status, output)."""
    sent = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName=SSM_DOCUMENT_NAME,
        Comment="Self-healing: restart NGINX",
        TimeoutSeconds=60,
    )
    command_id = sent["Command"]["CommandId"]
    logger.info("SSM command %s sent to %s", command_id, instance_id)

    deadline = time.time() + COMMAND_TIMEOUT_SECONDS
    status, output = "Pending", ""
    while time.time() < deadline:
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except Exception as exc:  # invocation may not exist yet
            logger.info("Invocation not ready yet: %s", exc)
            continue
        status = inv["Status"]
        output = (inv.get("StandardOutputContent") or inv.get("StandardErrorContent") or "").strip()
        if status in TERMINAL_STATES:
            break
    return status == "Success", status, output[-500:]


def reboot_instance(instance_id):
    ec2.reboot_instances(InstanceIds=[instance_id])
    return True, "RebootRequested", "EC2 reboot API call accepted"


# ---------------------------------------------------------------- handler
def lambda_handler(event, context):
    alarm = parse_alarm(event)
    logger.info("Received alarm: %s", json.dumps(alarm))

    if alarm["state"] != "ALARM":
        return {"action": "ignored", "reason": f"state is {alarm['state']}"}

    instance_id = alarm["instance_id"]
    if not instance_id:
        notify_slack(False, "Self-healing could not run", {
            "Alarm": alarm["alarm_name"],
            "Problem": "No InstanceId dimension on the alarm",
        })
        return {"action": "failed", "reason": "missing InstanceId"}

    started = time.time()
    try:
        if alarm["metric"] == "StatusCheckFailed_Instance":
            action = "Reboot instance"
            ok, status, output = reboot_instance(instance_id)
        else:
            action = "Restart NGINX via SSM"
            ok, status, output = restart_nginx(instance_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recovery action crashed")
        ok, status, output, action = False, "Exception", str(exc), "Recovery attempt"

    elapsed = f"{time.time() - started:.1f}s"
    title = "Recovery successful" if ok else "Recovery FAILED - manual action needed"
    notify_slack(ok, title, {
        "Instance": instance_id,
        "Alarm": alarm["alarm_name"],
        "Action": action,
        "Result": status,
        "Duration": elapsed,
        "Output": f"```{output or 'n/a'}```",
    })
    return {"action": action, "success": ok, "status": status}
