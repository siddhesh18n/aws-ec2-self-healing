# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Alarm stuck in `INSUFFICIENT_DATA` | CloudWatch agent not running or wrong dimensions | SSM into the instance: `sudo systemctl status amazon-cloudwatch-agent`. In the console check **CWAgent** namespace for `procstat_lookup_pid_count` and make sure its dimensions are exactly `InstanceId` + `exe=nginx`. |
| Alarm fires but nothing happens | SNS to Lambda not wired | Check Lambda CloudWatch logs `/aws/lambda/<project>-recovery`; confirm the SNS subscription is *Confirmed*. |
| `InvalidInstanceId` from SSM | Instance not registered with Systems Manager | Needs outbound internet/VPC endpoints and the `AmazonSSMManagedInstanceCore` role. Check Fleet Manager. |
| Recovery works but no Slack message | Webhook missing/invalid | Update the `/<project>/slack-webhook-url` SSM parameter; webhook must start with `https://`. |
| `AccessDenied` on `ssm:SendCommand` | IAM scope | The Lambda role is limited to the project's document and EC2 instances in the same account/region. |
| Alarm re-fires immediately | NGINX fails to start (bad config) | The SSM document runs `nginx -t` first; the Slack message shows the error output. |
