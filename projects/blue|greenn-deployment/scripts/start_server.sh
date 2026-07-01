#!/bin/bash
set -e

echo "=== Step 2: Starting Apache Web Server ==="
sudo systemctl enable httpd
sudo systemctl start httpd