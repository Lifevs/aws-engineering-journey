// Indexer Lambda: triggered by DynamoDB Streams (EventSourceMapping in CFN).
// Node 20.x runtime has global fetch built in - no bundling needed.

const ENDPOINT = process.env.OPENSEARCH_ENDPOINT;
const INDEX = process.env.INDEX_NAME || 'products';
const AUTH = Buffer.from(`${process.env.OPENSEARCH_USER}:${process.env.OPENSEARCH_PASS}`).toString('base64');

function unmarshallItem(image) {
  // Minimal DynamoDB-JSON -> plain JSON unmarshaller (avoids pulling in a package).
  const out = {};
  for (const [key, val] of Object.entries(image)) {
    const type = Object.keys(val)[0];
    const raw = val[type];
    if (type === 'S') out[key] = raw;
    else if (type === 'N') out[key] = Number(raw);
    else if (type === 'BOOL') out[key] = raw;
    else if (type === 'SS' || type === 'NS') out[key] = raw;
    else if (type === 'M') out[key] = unmarshallItem(raw);
    else if (type === 'L') out[key] = raw.map(v => unmarshallItem({ v })['v']);
    else out[key] = raw;
  }
  return out;
}

async function osRequest(method, path, body) {
  const res = await fetch(`https://${ENDPOINT}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Basic ${AUTH}`
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const text = await res.text();
  if (!res.ok) {
    console.error(`OpenSearch ${method} ${path} failed: ${res.status} ${text}`);
    throw new Error(`OpenSearch error ${res.status}`);
  }
  return text ? JSON.parse(text) : {};
}

export const handler = async (event) => {
  console.log(`Processing ${event.Records.length} stream record(s)`);

  for (const record of event.Records) {
    const id = record.dynamodb.Keys.id.S;

    if (record.eventName === 'INSERT' || record.eventName === 'MODIFY') {
      const doc = unmarshallItem(record.dynamodb.NewImage);
      await osRequest('PUT', `/${INDEX}/_doc/${encodeURIComponent(id)}`, doc);
      console.log(`Indexed id=${id} (${record.eventName})`);
    } else if (record.eventName === 'REMOVE') {
      try {
        await osRequest('DELETE', `/${INDEX}/_doc/${encodeURIComponent(id)}`);
        console.log(`Deleted id=${id}`);
      } catch (err) {
        // 404 on delete is fine (doc never made it in, or already removed)
        console.warn(`Delete for id=${id} failed (may already be absent): ${err.message}`);
      }
    }
  }

  return { statusCode: 200, processed: event.Records.length };
};
