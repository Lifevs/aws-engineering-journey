#!/bin/bash
set -e
echo "Starting application..."

# Example using a systemd service named myapp.service that runs `node server.js`
# Create /etc/systemd/system/myapp.service ahead of time (via AMI or first-run setup)
systemctl daemon-reload
systemctl start myapp
systemctl enable myapp
