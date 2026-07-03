#!/bin/bash
set -e
echo "Preparing instance for new deployment..."

# Stop existing app if running
if systemctl is-active --quiet myapp; then
  systemctl stop myapp
fi

# Clean out old deployment
rm -rf /home/ec2-user/app
mkdir -p /home/ec2-user/app
