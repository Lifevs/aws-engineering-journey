"use strict";

/**
 * app.js — Production CRUD Lambda Handler
 * Runtime : Node.js 20.x (arm64 / Graviton2)
 * Service : Items CRUD Backend
 *
 * Architecture notes:
 *  • DynamoDB DocumentClient is initialised ONCE in module scope so that the
 *    underlying TCP/TLS connection is reused across warm invocations.
 *  • Every log statement is a structured JSON object written to stdout so that
 *    CloudWatch Logs Insights can parse and query fields without transforms.
 *  • All errors are caught at the handler boundary; no unhandled rejections.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Module-scope initialisation  (runs once per cold start, reused on warm starts)
// ─────────────────────────────────────────────────────────────────────────────
const { DynamoDBClient }            = require("@aws-sdk/client-dynamodb");
const {
  DynamoDBDocumentClient,
  PutCommand,
  GetCommand,
  UpdateCommand,
  DeleteCommand,
  ScanCommand,
}                                   = require("@aws-sdk/lib-dynamodb");
const { randomUUID }                = require("crypto");

// Instantiate the low-level client outside handler scope → connection reuse
const rawClient = new DynamoDBClient({
  region: process.env.AWS_REGION ?? "us-east-1",
  // SDK v3 uses keep-alive by default via undici; no extra config required.
});

// Wrap with DocumentClient for automatic marshalling/unmarshalling
const ddb = DynamoDBDocumentClient.from(rawClient, {
  marshallOptions:   { removeUndefinedValues: true, convertEmptyValues: false },
  unmarshallOptions: { wrapNumbers: false },
});

const TABLE_NAME = process.env.TABLE_NAME;

// ─────────────────────────────────────────────────────────────────────────────
// Structured logger — emits JSON to stdout (picked up by CloudWatch Logs)
// ─────────────────────────────────────────────────────────────────────────────
const log = (level, event, context = {}) => {
  const entry = {
    timestamp:  new Date().toISOString(),
    level:      level.toUpperCase(),
    event,
    service:    process.env.POWERTOOLS_SERVICE_NAME ?? "crud-backend",
    ...context,
  };
  // Use a single process.stdout.write to avoid interleaving in concurrent envs
  process.stdout.write(JSON.stringify(entry) + "\n");
};

const logger = {
  info:  (event, ctx) => log("INFO",  event, ctx),
  warn:  (event, ctx) => log("WARN",  event, ctx),
  error: (event, ctx) => log("ERROR", event, ctx),
  debug: (event, ctx) => log("DEBUG", event, ctx),
};

// ─────────────────────────────────────────────────────────────────────────────
// HTTP response builder
// ─────────────────────────────────────────────────────────────────────────────
const buildResponse = (statusCode, body, requestId) => ({
  statusCode,
  headers: {
    "Content-Type":                "application/json",
    "X-Request-Id":                requestId,
    "Access-Control-Allow-Origin": "*",
  },
  body: JSON.stringify(body),
});

// ─────────────────────────────────────────────────────────────────────────────
// CRUD operation implementations
// ─────────────────────────────────────────────────────────────────────────────

/**
 * CREATE — POST /items
 * Body: { name: string, description?: string }
 */
const createItem = async (body, requestId) => {
  const itemId      = randomUUID();
  const now         = new Date().toISOString();
  const { name, description = "" } = body;

  if (!name || typeof name !== "string" || name.trim() === "") {
    return buildResponse(400, { error: "Validation", message: "Field 'name' is required and must be a non-empty string." }, requestId);
  }

  const item = { itemId, name: name.trim(), description: description.trim(), createdAt: now, updatedAt: now };

  logger.info("DB_OPERATION_INITIATED", {
    requestId,
    action:       "PutItem",
    partitionKey: itemId,
    tableName:    TABLE_NAME,
    payload:      { name: item.name, descriptionLength: item.description.length },
  });

  const command = new PutCommand({ TableName: TABLE_NAME, Item: item, ConditionExpression: "attribute_not_exists(itemId)" });
  await ddb.send(command);

  logger.info("DB_OPERATION_SUCCESS", {
    requestId,
    action:    "PutItem",
    itemId,
    createdAt: now,
  });

  return buildResponse(201, { message: "Item created successfully.", item }, requestId);
};

/**
 * READ (single) — GET /items/{itemId}
 */
const getItem = async (itemId, requestId) => {
  logger.info("DB_OPERATION_INITIATED", {
    requestId,
    action:       "GetItem",
    partitionKey: itemId,
    tableName:    TABLE_NAME,
  });

  const command = new GetCommand({ TableName: TABLE_NAME, Key: { itemId } });
  const result  = await ddb.send(command);

  if (!result.Item) {
    logger.warn("DB_OPERATION_NOT_FOUND", { requestId, action: "GetItem", itemId });
    return buildResponse(404, { error: "Not Found", message: `Item '${itemId}' does not exist.` }, requestId);
  }

  logger.info("DB_OPERATION_SUCCESS", {
    requestId,
    action:    "GetItem",
    itemId,
    foundAt:   result.Item.createdAt,
  });

  return buildResponse(200, { item: result.Item }, requestId);
};

/**
 * LIST — GET /items
 * Uses DynamoDB Scan with pagination support via LastEvaluatedKey.
 * For tables > ~1 MB, clients should pass ?lastKey=<base64-encoded-key>.
 */
const listItems = async (queryParams, requestId) => {
  const limit       = Math.min(parseInt(queryParams?.limit ?? "50", 10), 100);
  const rawLastKey  = queryParams?.lastKey;
  let   exclusiveStartKey;

  if (rawLastKey) {
    try {
      exclusiveStartKey = JSON.parse(Buffer.from(rawLastKey, "base64url").toString("utf-8"));
    } catch {
      return buildResponse(400, { error: "Bad Request", message: "Invalid 'lastKey' pagination token." }, requestId);
    }
  }

  logger.info("DB_OPERATION_INITIATED", {
    requestId,
    action:    "Scan",
    tableName: TABLE_NAME,
    limit,
    hasPaginationToken: !!exclusiveStartKey,
  });

  const params = { TableName: TABLE_NAME, Limit: limit };
  if (exclusiveStartKey) params.ExclusiveStartKey = exclusiveStartKey;

  const command = new ScanCommand(params);
  const result  = await ddb.send(command);

  const nextKey = result.LastEvaluatedKey
    ? Buffer.from(JSON.stringify(result.LastEvaluatedKey)).toString("base64url")
    : null;

  logger.info("DB_OPERATION_SUCCESS", {
    requestId,
    action:    "Scan",
    count:     result.Count,
    scanned:   result.ScannedCount,
    hasMore:   !!nextKey,
  });

  return buildResponse(200, {
    items:   result.Items ?? [],
    count:   result.Count,
    ...(nextKey && { nextKey }),
  }, requestId);
};

/**
 * UPDATE — PUT /items/{itemId}
 * Body: { name?: string, description?: string }
 * Only provided fields are updated (partial update via expression attributes).
 */
const updateItem = async (itemId, body, requestId) => {
  const updates = {};
  if (body.name        !== undefined) updates.name        = String(body.name).trim();
  if (body.description !== undefined) updates.description = String(body.description).trim();

  if (Object.keys(updates).length === 0) {
    return buildResponse(400, { error: "Bad Request", message: "At least one field ('name' or 'description') must be provided for update." }, requestId);
  }

  updates.updatedAt = new Date().toISOString();

  // Build a dynamic UpdateExpression from the provided keys
  const expressionParts   = [];
  const expressionNames   = {};
  const expressionValues  = {};

  Object.entries(updates).forEach(([key, value]) => {
    const nameToken  = `#${key}`;
    const valueToken = `:${key}`;
    expressionParts.push(`${nameToken} = ${valueToken}`);
    expressionNames[nameToken]  = key;
    expressionValues[valueToken] = value;
  });

  logger.info("DB_OPERATION_INITIATED", {
    requestId,
    action:       "UpdateItem",
    partitionKey: itemId,
    tableName:    TABLE_NAME,
    fieldsUpdated: Object.keys(updates).filter(k => k !== "updatedAt"),
  });

  const command = new UpdateCommand({
    TableName:                 TABLE_NAME,
    Key:                       { itemId },
    UpdateExpression:          `SET ${expressionParts.join(", ")}`,
    ExpressionAttributeNames:  expressionNames,
    ExpressionAttributeValues: expressionValues,
    ConditionExpression:       "attribute_exists(itemId)",  // Prevent upsert; item must exist
    ReturnValues:              "ALL_NEW",
  });

  const result = await ddb.send(command);

  logger.info("DB_OPERATION_SUCCESS", {
    requestId,
    action:    "UpdateItem",
    itemId,
    updatedAt: updates.updatedAt,
    attributes: Object.keys(result.Attributes ?? {}),
  });

  return buildResponse(200, { message: "Item updated successfully.", item: result.Attributes }, requestId);
};

/**
 * DELETE — DELETE /items/{itemId}
 */
const deleteItem = async (itemId, requestId) => {
  logger.info("DB_OPERATION_INITIATED", {
    requestId,
    action:       "DeleteItem",
    partitionKey: itemId,
    tableName:    TABLE_NAME,
  });

  const command = new DeleteCommand({
    TableName:           TABLE_NAME,
    Key:                 { itemId },
    ConditionExpression: "attribute_exists(itemId)",  // Return 404 if item doesn't exist
    ReturnValues:        "ALL_OLD",
  });

  const result = await ddb.send(command);

  logger.info("DB_OPERATION_SUCCESS", {
    requestId,
    action:  "DeleteItem",
    itemId,
    deletedItemName: result.Attributes?.name ?? "unknown",
  });

  return buildResponse(200, { message: "Item deleted successfully.", itemId }, requestId);
};

// ─────────────────────────────────────────────────────────────────────────────
// Conditional expression error classifier
// Maps DynamoDB conditional check failures to appropriate HTTP responses
// ─────────────────────────────────────────────────────────────────────────────
const classifyDynamoError = (err, itemId) => {
  if (err.name === "ConditionalCheckFailedException") {
    return { statusCode: 409, message: `Conflict: item '${itemId}' either already exists or was not found.` };
  }
  if (err.name === "ProvisionedThroughputExceededException" || err.name === "RequestLimitExceeded") {
    return { statusCode: 503, message: "Service temporarily unavailable. Please retry with exponential backoff." };
  }
  if (err.name === "ResourceNotFoundException") {
    return { statusCode: 500, message: "Internal configuration error: DynamoDB table not found." };
  }
  return { statusCode: 500, message: "An unexpected error occurred." };
};

// ─────────────────────────────────────────────────────────────────────────────
// Lambda Handler — single entry point (API Gateway Lambda Proxy integration)
// ─────────────────────────────────────────────────────────────────────────────
exports.handler = async (event, context) => {
  const requestId  = context.awsRequestId;
  const httpMethod = event.httpMethod;
  const resource   = event.resource;
  const path       = event.path;
  const itemId     = event.pathParameters?.itemId;

  // ── Lifecycle: 1. Invocation received ─────────────────────────────────────
  logger.info("LAMBDA_INVOKED", {
    requestId,
    httpMethod,
    resource,
    path,
    pathParameters:      event.pathParameters ?? {},
    queryStringParams:   event.queryStringParameters ?? {},
    sourceIp:            event.requestContext?.identity?.sourceIp ?? "unknown",
    userAgent:           event.requestContext?.identity?.userAgent ?? "unknown",
    stage:               event.requestContext?.stage ?? "unknown",
    apiGwRequestId:      event.requestContext?.requestId ?? "unknown",
  });

  // ── Lifecycle: 2. SDK client health check ─────────────────────────────────
  logger.info("SDK_CLIENT_CHECK", {
    requestId,
    clientInitialised: !!ddb,
    tableName:         TABLE_NAME,
    region:            process.env.AWS_REGION,
  });

  if (!TABLE_NAME) {
    logger.error("CONFIGURATION_ERROR", { requestId, message: "TABLE_NAME environment variable is not set." });
    const response = buildResponse(500, { error: "Configuration Error", message: "Server misconfiguration." }, requestId);
    logger.info("RESPONSE_DISPATCHED", { requestId, statusCode: response.statusCode });
    return response;
  }

  // ── Route + execute ───────────────────────────────────────────────────────
  let response;

  try {
    // Parse body once — safe to call on undefined (list/get/delete have no body)
    let body = {};
    if (event.body) {
      try {
        body = JSON.parse(event.body);
      } catch {
        response = buildResponse(400, { error: "Bad Request", message: "Request body is not valid JSON." }, requestId);
        logger.info("RESPONSE_DISPATCHED", { requestId, statusCode: response.statusCode, reason: "INVALID_JSON_BODY" });
        return response;
      }
    }

    if      (httpMethod === "POST"   && resource === "/items")          response = await createItem(body, requestId);
    else if (httpMethod === "GET"    && resource === "/items/{itemId}")  response = await getItem(itemId, requestId);
    else if (httpMethod === "GET"    && resource === "/items")           response = await listItems(event.queryStringParameters, requestId);
    else if (httpMethod === "PUT"    && resource === "/items/{itemId}")  response = await updateItem(itemId, body, requestId);
    else if (httpMethod === "DELETE" && resource === "/items/{itemId}")  response = await deleteItem(itemId, requestId);
    else {
      logger.warn("ROUTE_NOT_MATCHED", { requestId, httpMethod, resource });
      response = buildResponse(405, { error: "Method Not Allowed", message: `${httpMethod} ${resource} is not a supported route.` }, requestId);
    }

  } catch (err) {
    // ── Lifecycle: 5. Exception caught ─────────────────────────────────────
    const { statusCode, message } = classifyDynamoError(err, itemId);

    logger.error("EXCEPTION_CAUGHT", {
      requestId,
      errorName:    err.name,
      errorCode:    err.$metadata?.httpStatusCode ?? "N/A",
      errorMessage: err.message,
      stack:        err.stack,
      httpMethod,
      resource,
      itemId:       itemId ?? "N/A",
    });

    response = buildResponse(statusCode, { error: err.name, message }, requestId);
  }

  // ── Lifecycle: 6. Response dispatched ──────────────────────────────────────
  logger.info("RESPONSE_DISPATCHED", {
    requestId,
    statusCode:      response.statusCode,
    bodyByteLength:  response.body ? Buffer.byteLength(response.body, "utf-8") : 0,
  });

  return response;
};
