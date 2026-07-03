async function loadInstanceInfo() {
  const sourceEl = document.getElementById('pass-source');
  try {
    const res = await fetch('/api/instance-info');
    const data = await res.json();

    setText('pass-region', data.region);
    setText('pass-az', data.availabilityZone);
    setText('pass-instance-id', data.instanceId);
    setText('pass-instance-type', data.instanceType);
    setText('pass-public-ip', data.publicIp);
    setText('pass-local-ip', data.localIp);
    setText('pass-hostname', data.hardware.hostname);
    setText('pass-cpu', shortenCpu(data.hardware.cpuModel));
    setText('pass-cores', data.hardware.cpuCores);
    setText('pass-memory', `${data.hardware.freeMemoryGB} / ${data.hardware.totalMemoryGB} GB free`);
    setText('pass-uptime', formatUptime(data.hardware.uptimeMinutes));

    sourceEl.textContent = data.source === 'ec2-imds'
      ? 'verified via EC2 instance metadata'
      : 'local dev — not running on EC2';
  } catch (err) {
    sourceEl.textContent = 'could not reach /api/instance-info';
    console.error(err);
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function shortenCpu(model) {
  if (!model) return 'unknown';
  return model.length > 28 ? model.slice(0, 28) + '…' : model;
}

function formatUptime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

loadInstanceInfo();
