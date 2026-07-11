const { Pool } = require('pg');
const { SecretsManagerClient, GetSecretValueCommand } = require("@aws-sdk/client-secrets-manager");

const secretsClient = new SecretsManagerClient({ region: process.env.AWS_REGION });
let pool;

// Function to fetch credentials from Secrets Manager at runtime
async function getDatabaseSecret() {
  const secretName = "app-db-credentials-secret-v2"; 
  const response = await secretsClient.send(new GetSecretValueCommand({ SecretId: secretName }));
  return JSON.parse(response.SecretString);
}

exports.handler = async (event, context) => {
  // Initialize the connection pool once across warm containers
  if (!pool) {
    try {
      const credentials = await getDatabaseSecret();
      pool = new Pool({
        host: process.env.DB_HOST, // Points to the RDS Proxy Endpoint
        user: credentials.username,
        password: credentials.password,
        database: 'postgres',
        port: 5432,
        max: 5, // Maximum connections allowed per Lambda container instance
        idleTimeoutMillis: 30000,
      });
    } catch (err) {
      console.error("Failed to initialize database connection pool:", err);
      throw err;
    }
  }

  const client = await pool.connect();

  try {
    // 1. Create a log table if it doesn't already exist
    await client.query(`
      CREATE TABLE IF NOT EXISTS proxy_traffic_logs (
        id SERIAL PRIMARY KEY,
        lambda_request_id TEXT NOT NULL,
        executed_at TIMESTAMP DEFAULT NOW()
      );
    `);

    // 2. Populate data: Insert a row tracking this specific invocation
    await client.query(
      'INSERT INTO proxy_traffic_logs (lambda_request_id) VALUES ($1);',
      [context.awsRequestId]
    );

    // 3. Count total items populated so far
    const countResult = await client.query('SELECT COUNT(*) FROM proxy_traffic_logs;');
    const totalRows = countResult.rows[0].count;

    // 4. THE PROXY VERIFICATION METRIC:
    // Query the DB's internal metrics to see how many physical connections are open right now.
    const connectionsResult = await client.query(`
      SELECT count(*) FROM pg_stat_activity 
      WHERE usename = 'postgresadmin' AND application_name NOT LIKE 'CloudWatch%';
    `);
    const openBackendConnections = connectionsResult.rows[0].count;

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "Success",
        proxy_endpoint_used: process.env.DB_HOST,
        lambda_request_id: context.awsRequestId,
        total_records_populated: parseInt(totalRows, 10),
        actual_open_connections_on_database: parseInt(openBackendConnections, 10),
        explanation: "If this number stays low while executing huge concurrent loads, the proxy is successfully multiplexing connections."
      })
    };

  } catch (error) {
    console.error("Execution error:", error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message })
    };
  } finally {
    // Release the client back to the local Lambda execution pool
    client.release();
  }
};