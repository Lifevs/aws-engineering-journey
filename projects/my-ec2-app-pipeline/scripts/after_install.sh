#!/bin/bash
set -e
echo "Running post-install steps..."

cd /home/ec2-user/app

# Install runtime dependencies on the instance (production only)
if [ -f package.json ]; then
  npm install --omit=dev
fi

chown -R ec2-user:ec2-user /home/ec2-user/app
