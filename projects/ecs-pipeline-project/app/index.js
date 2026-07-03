const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

// Version string is baked in at build time via env var so you can visibly
// confirm a rolling deploy actually shipped new code.
const APP_VERSION = process.env.APP_VERSION || 'local-dev';

app.get('/', (req, res) => {
  res.json({
    message: 'Hello from ECS Fargate!',
    version: APP_VERSION,
    hostname: require('os').hostname(),
    timestamp: new Date().toISOString()
  });
});

// ECS health check target
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy' });
});

app.listen(PORT, () => {
  console.log(`App listening on port ${PORT}, version ${APP_VERSION}`);
});
