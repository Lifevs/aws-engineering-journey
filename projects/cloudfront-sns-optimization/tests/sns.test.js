const { buildMessageAttributes } = require('../app/sns');

describe('buildMessageAttributes', () => {
  test('builds attributes SNS filter policies can match on', () => {
    const attrs = buildMessageAttributes({
      eventType: 'price_updated',
      priceChangeType: 'increase',
      region: 'ap-south-1',
    });

    expect(attrs).toEqual({
      eventType: { DataType: 'String', StringValue: 'price_updated' },
      priceChangeType: { DataType: 'String', StringValue: 'increase' },
      region: { DataType: 'String', StringValue: 'ap-south-1' },
    });
  });

  test('omits attributes that are not provided', () => {
    const attrs = buildMessageAttributes({ eventType: 'stock_updated' });

    expect(attrs).toEqual({
      eventType: { DataType: 'String', StringValue: 'stock_updated' },
    });
    expect(attrs.priceChangeType).toBeUndefined();
    expect(attrs.region).toBeUndefined();
  });

  // This simulates SNS's own filter-policy evaluation logic so you can
  // sanity-check your attributes will match/not-match BEFORE deploying,
  // instead of debugging silently-dropped messages in production.
  function wouldMatch(filterPolicy, messageAttributes) {
    return Object.entries(filterPolicy).every(([attrKey, allowedValues]) => {
      const actual = messageAttributes[attrKey];
      if (!actual) return false;
      return allowedValues.includes(actual.StringValue);
    });
  }

  test('a subscriber filtering on price increases only receives increase events', () => {
    const filterPolicy = { eventType: ['price_updated'], priceChangeType: ['increase'] };

    const increaseMsg = buildMessageAttributes({
      eventType: 'price_updated',
      priceChangeType: 'increase',
    });
    const decreaseMsg = buildMessageAttributes({
      eventType: 'price_updated',
      priceChangeType: 'decrease',
    });
    const stockMsg = buildMessageAttributes({ eventType: 'stock_updated' });

    expect(wouldMatch(filterPolicy, increaseMsg)).toBe(true);
    expect(wouldMatch(filterPolicy, decreaseMsg)).toBe(false);
    expect(wouldMatch(filterPolicy, stockMsg)).toBe(false);
  });
});
