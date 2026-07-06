const { SNSClient, PublishCommand } = require('@aws-sdk/client-sns');

const client = new SNSClient({ region: process.env.AWS_REGION || 'ap-south-1' });

/**
 * Builds the MessageAttributes object SNS uses to evaluate subscription
 * filter policies. Filter policies are matched against these attributes,
 * NOT against the message body - this is the #1 thing people get wrong.
 *
 * Example filter policy on a subscription:
 *   { "eventType": ["price_updated"], "priceChangeType": ["increase"] }
 * A message published with attributes eventType=price_updated and
 * priceChangeType=increase will match; eventType=stock_updated will not,
 * so that subscriber's Lambda/SQS never even gets invoked - this is the
 * "reduce processing" cost/perf win the task refers to.
 */
function buildMessageAttributes({ eventType, priceChangeType, region }) {
  const attrs = {};
  if (eventType) {
    attrs.eventType = { DataType: 'String', StringValue: eventType };
  }
  if (priceChangeType) {
    attrs.priceChangeType = { DataType: 'String', StringValue: priceChangeType };
  }
  if (region) {
    attrs.region = { DataType: 'String', StringValue: region };
  }
  return attrs;
}

async function publishProductEvent(topicArn, payload, attributeInput) {
  const command = new PublishCommand({
    TopicArn: topicArn,
    Message: JSON.stringify(payload),
    MessageAttributes: buildMessageAttributes(attributeInput),
  });
  return client.send(command);
}

module.exports = { buildMessageAttributes, publishProductEvent, client };
