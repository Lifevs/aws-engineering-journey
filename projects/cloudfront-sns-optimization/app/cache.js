const Redis = require('ioredis');

// In production this points at your ElastiCache Redis primary endpoint.
// Locally it points at the redis container from docker-compose.yml.
const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  // ElastiCache in-transit encryption uses TLS - uncomment for real clusters:
  // tls: process.env.REDIS_TLS === 'true' ? {} : undefined,
  lazyConnect: false,
  maxRetriesPerRequest: 2,
});

// Simple in-process counters. In real deployments you'd push these as
// CustomMetrics to CloudWatch (see infra/README notes) instead of keeping
// them in memory, since memory resets on redeploy/restart.
const metrics = { hits: 0, misses: 0 };

function getHitRate() {
  const total = metrics.hits + metrics.misses;
  if (total === 0) return { hits: 0, misses: 0, hitRatePercent: 0 };
  return {
    hits: metrics.hits,
    misses: metrics.misses,
    hitRatePercent: Number(((metrics.hits / total) * 100).toFixed(2)),
  };
}

/**
 * Cache-aside (lazy loading) pattern: check Redis first, fall back to the
 * loader function (RDS query) on a miss, then populate the cache with a TTL.
 *
 * @param {string} key       cache key, e.g. "product:1"
 * @param {number} ttlSeconds
 * @param {Function} loader  async function that fetches from RDS on a miss
 */
async function cacheAside(key, ttlSeconds, loader) {
  const cached = await redis.get(key);
  if (cached !== null) {
    metrics.hits += 1;
    return { data: JSON.parse(cached), source: 'cache' };
  }

  metrics.misses += 1;
  const fresh = await loader();
  if (fresh !== null && fresh !== undefined) {
    await redis.set(key, JSON.stringify(fresh), 'EX', ttlSeconds);
  }
  return { data: fresh, source: 'database' };
}

async function invalidate(key) {
  await redis.del(key);
}

module.exports = { redis, cacheAside, invalidate, getHitRate, metrics };
