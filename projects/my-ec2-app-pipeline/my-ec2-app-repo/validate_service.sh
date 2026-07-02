#!/bin/bash
set -e
echo "Validating deployment..."

# Give the app a moment to boot
sleep 5

# Basic health check - adjust the port/path to match your app
if curl -sf http://localhost:80/health > /dev/null; then
  echo "Health check passed."
  exit 0
else
  echo "Health check failed."
  exit 1
fi
