const express = require('express');
const os = require('os');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 80;

app.use(express.static(path.join(__dirname, 'public')));

// CodeDeploy validate_service.sh hits this
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

// IMDSv2: get a session token, then use it to read metadata
async function getMetadataToken() {
  const res = await fetch('http://169.254.169.254/latest/api/token', {
    method: 'PUT',
    headers: { 'X-aws-ec2-metadata-token-ttl-seconds': '21600' },
    signal: AbortSignal.timeout(1000),
  });
  if (!res.ok) throw new Error('token fetch failed');
  return res.text();
}

async function getMetadata(path, token) {
  const res = await fetch(`http://169.254.169.254/latest/meta-data/${path}`, {
    headers: { 'X-aws-ec2-metadata-token': token },
    signal: AbortSignal.timeout(1000),
  });
  if (!res.ok) throw new Error(`metadata fetch failed for ${path}`);
  return res.text();
}

app.get('/api/instance-info', async (req, res) => {
  const hardware = {
    hostname: os.hostname(),
    platform: os.platform(),
    arch: os.arch(),
    cpuModel: os.cpus()[0] ? os.cpus()[0].model : 'unknown',
    cpuCores: os.cpus().length,
    totalMemoryGB: (os.totalmem() / (1024 ** 3)).toFixed(2),
    freeMemoryGB: (os.freemem() / (1024 ** 3)).toFixed(2),
    uptimeMinutes: Math.floor(os.uptime() / 60),
  };

  try {
    const token = await getMetadataToken();
    const [
      instanceId,
      instanceType,
      region,
      az,
      localIp,
      publicIp,
    ] = await Promise.all([
      getMetadata('instance-id', token),
      getMetadata('instance-type', token),
      getMetadata('placement/region', token),
      getMetadata('placement/availability-zone', token),
      getMetadata('local-ipv4', token),
      getMetadata('public-ipv4', token).catch(() => 'none (no public IP assigned)'),
    ]);

    return res.json({
      source: 'ec2-imds',
      instanceId,
      instanceType,
      region,
      availabilityZone: az,
      localIp,
      publicIp,
      hardware,
    });
  } catch (err) {
    // Not running on EC2 (e.g. local dev) — return host info with a flag
    return res.json({
      source: 'local-fallback',
      instanceId: 'n/a (not running on EC2)',
      instanceType: 'n/a',
      region: 'n/a',
      availabilityZone: 'n/a',
      localIp: 'n/a',
      publicIp: 'n/a',
      hardware,
    });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
