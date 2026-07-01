#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Step 1: Updating packages and installing Apache ==="
sudo yum update -y
sudo yum install -y httpd

# Clear out any default placeholder files to prevent conflicts
sudo rm -rf /var/www/html/*