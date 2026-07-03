#!/bin/bash
set -e
echo "Running post-install steps..."

cd /home/ec2-user/app

# Defensive: ensure Node + libcap are present, and Node can bind to port 80
# without running as root (setcap is wiped if node is ever reinstalled).
if ! command -v node &> /dev/null; then
  sudo yum install -y nodejs
fi
sudo yum install -y libcap
sudo setcap 'cap_net_bind_service=+ep' "$(readlink -f "$(which node)")"

# Install runtime dependencies on the instance (production only)
if [ -f package.json ]; then
  npm install --omit=dev
fi

chown -R ec2-user:ec2-user /home/ec2-user/app