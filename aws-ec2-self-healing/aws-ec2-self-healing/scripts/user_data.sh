#!/bin/bash
# EC2 bootstrap: install NGINX + CloudWatch agent (rendered by Terraform templatefile)
set -euxo pipefail

dnf install -y nginx amazon-cloudwatch-agent

cat > /usr/share/nginx/html/index.html <<'HTML'
<!DOCTYPE html>
<html><head><title>Self-Healing NGINX</title></head>
<body style="font-family:sans-serif;text-align:center;margin-top:15%">
<h1>NGINX is up</h1><p>Protected by CloudWatch + Lambda + Systems Manager</p>
</body></html>
HTML

systemctl enable --now nginx

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -c ssm:${cwagent_param} -s
