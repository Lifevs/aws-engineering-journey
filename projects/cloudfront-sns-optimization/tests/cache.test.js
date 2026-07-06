// Mock ioredis so tests run without a real Redis/ElastiCache instance.
jest.mock('ioredis', () => {
  const store = new Map();
  return jest.fn().mockImplementation(() => ({
    get: jest.fn(async (key) => (store.has(key) ? store.get(key) : null)),
    set: jest.fn(async (key, value) => {
      store.set(key, value);
      return 'OK';
    }),
    del: jest.fn(async (key) => {
      store.delete(key);
      return 1;
    }),
  }));
});

const { cacheAside, invalidate, getHitRate, metrics } = require('../app/cache');

describe('cacheAside', () => {
  beforeEach(() => {
    metrics.hits = 0;
    metrics.misses = 0;
  });

  test('miss: calls the loader and populates the cache', async () => {
    const loader = jest.fn().mockResolvedValue({ id: 1, name: 'Widget', price: 9.99 });

    const result = await cacheAside('product:1:usd', 60, loader);

    expect(loader).toHaveBeenCalledTimes(1);
    expect(result.source).toBe('database');
    expect(result.data).toEqual({ id: 1, name: 'Widget', price: 9.99 });
  });

  test('hit: second call for the same key does NOT call the loader again', async () => {
    const loader = jest.fn().mockResolvedValue({ id: 2, name: 'Gadget', price: 14.5 });

    await cacheAside('product:2:usd', 60, loader); // populates cache
    const second = await cacheAside('product:2:usd', 60, loader); // should hit

    expect(loader).toHaveBeenCalledTimes(1); // NOT called again
    expect(second.source).toBe('cache');
    expect(second.data).toEqual({ id: 2, name: 'Gadget', price: 14.5 });
  });

  test('invalidate() forces the next read to be a miss again', async () => {
    const loader = jest.fn().mockResolvedValue({ id: 3, name: 'Doohickey', price: 5 });

    await cacheAside('product:3:usd', 60, loader);
    await invalidate('product:3:usd');
    await cacheAside('product:3:usd', 60, loader);

    expect(loader).toHaveBeenCalledTimes(2); // miss, then miss again after invalidation
  });

  test('getHitRate() reports accurate hit/miss ratio', async () => {
    const loader = jest.fn().mockResolvedValue({ id: 4, name: 'Thingamajig', price: 1 });

    await cacheAside('product:4:usd', 60, loader); // miss
    await cacheAside('product:4:usd', 60, loader); // hit
    await cacheAside('product:4:usd', 60, loader); // hit

    const stats = getHitRate();
    expect(stats.hits).toBe(2);
    expect(stats.misses).toBe(1);
    expect(stats.hitRatePercent).toBeCloseTo(66.67, 1);
  });
});
