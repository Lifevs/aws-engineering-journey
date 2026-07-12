// Search API Lambda: behind API Gateway HTTP API route GET /search?q=...
const ENDPOINT = process.env.OPENSEARCH_ENDPOINT;
const INDEX = process.env.INDEX_NAME || 'products';
const AUTH = Buffer.from(`${process.env.OPENSEARCH_USER}:${process.env.OPENSEARCH_PASS}`).toString('base64');

export const handler = async (event) => {
  const q = event.queryStringParameters?.q;
  const category = event.queryStringParameters?.category;

  if (!q) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'missing required query param: q' })
    };
  }

  const must = [
    {
      multi_match: {
        query: q,
        fields: ['name^2', 'description', 'tags'],
        fuzziness: 'AUTO'
      }
    }
  ];
  if (category) {
    must.push({ term: { 'category.keyword': category } });
  }

  const query = { query: { bool: { must } }, size: 20 };

  const started = Date.now();
  const res = await fetch(`https://${ENDPOINT}/${INDEX}/_search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Basic ${AUTH}`
    },
    body: JSON.stringify(query)
  });
  const took_ms_roundtrip = Date.now() - started;

  const data = await res.json();
  if (!res.ok) {
    return { statusCode: 502, body: JSON.stringify({ error: 'opensearch query failed', detail: data }) };
  }

  const hits = data.hits.hits.map(h => ({ id: h._id, score: h._score, ...h._source }));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: q,
      total: data.hits.total.value,
      opensearch_took_ms: data.took,
      lambda_roundtrip_ms: took_ms_roundtrip,
      results: hits
    })
  };
};
