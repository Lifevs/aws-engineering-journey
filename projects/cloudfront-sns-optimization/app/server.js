require('dotenv').config();
const express = require('express');
const { waitForDb, initSchema, getProductById, updateProductPrice } = require('./db');
const { cacheAside, invalidate, getHitRate } = require('./cache');
const { publishProductEvent } = require('./sns');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const CACHE_TTL_SECONDS = 60;
const SNS_TOPIC_ARN = process.env.SNS_TOPIC_ARN; // set after infra/create-resources.sh

app.get('/health', (req, res) => res.json({ status: 'ok' }));

/**
 * GET /products/:id
 * - Origin fetch (RDS via ElastiCache cache-aside).
 * - Sets Cache-Control + Vary headers so CloudFront's cache policy
 *   (which forwards the Accept-Language header and the "currency"
 *   query string) can build correct, distinct cache keys per variant.
 */
app.get('/products/:id', async (req, res) => {
  const { id } = req.params;
  const currency = req.query.currency || 'usd';
  const cacheKey = `product:${id}:${currency}`;

  try {
    const result = await cacheAside(cacheKey, CACHE_TTL_SECONDS, () => getProductById(id));
    if (!result.data) return res.status(404).json({ error: 'Product not found' });

    // These headers are what CloudFront's cache policy actually reads.
    res.set('Cache-Control', `public, max-age=${CACHE_TTL_SECONDS}`);
    res.set('Vary', 'Accept-Language');
    res.set('X-Cache-Source', result.source); // handy for verifying hit/miss while testing
    res.json(result.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * PATCH /products/:id/price
 * - Writes through to RDS, invalidates the Redis entry, and publishes an
 *   SNS event with attributes so filter-policy subscribers only react to
 *   the event types/regions they actually care about.
 */
app.patch('/products/:id/price', async (req, res) => {
  const { id } = req.params;
  const { price, region } = req.body;

  try {
    const existing = await getProductById(id);
    if (!existing) return res.status(404).json({ error: 'Product not found' });

    const updated = await updateProductPrice(id, price);
    await invalidate(`product:${id}:usd`);
    await invalidate(`product:${id}:inr`);

    if (SNS_TOPIC_ARN) {
      const priceChangeType = price > existing.price ? 'increase' : 'decrease';
      await publishProductEvent(
        SNS_TOPIC_ARN,
        { productId: id, oldPrice: existing.price, newPrice: price },
        { eventType: 'price_updated', priceChangeType, region: region || 'ap-south-1' }
      );
    }

    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Exposes counters for you to eyeball while load-testing; wire the same
// numbers to CloudWatch PutMetricData in production for real dashboards.
app.get('/metrics/cache', (req, res) => res.json(getHitRate()));

async function start() {
  await waitForDb();     // retries with backoff instead of crashing on first attempt
  await initSchema();
  app.listen(PORT, () => console.log(`Listening on :${PORT}`));
}

if (require.main === module) {
  start();
}

module.exports = { app };
