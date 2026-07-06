const { Pool } = require('pg');

// This pool talks to RDS in production, or the local Postgres container
// (see docker-compose.yml) for local testing.
const pool = new Pool({
  host: process.env.PGHOST || 'localhost',
  port: process.env.PGPORT || 5432,
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
  database: process.env.PGDATABASE || 'appdb',
  max: 10,
  idleTimeoutMillis: 30000,
});

async function initSchema() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS products (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      price NUMERIC NOT NULL,
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);
  // Seed a couple of rows if empty, so the demo has something to fetch/cache.
  const { rows } = await pool.query('SELECT COUNT(*)::int AS count FROM products');
  if (rows[0].count === 0) {
    await pool.query(
      `INSERT INTO products (name, price) VALUES
       ('Wireless Mouse', 19.99),
       ('Mechanical Keyboard', 89.50),
       ('USB-C Hub', 34.25)`
    );
  }
}

async function getProductById(id) {
  const { rows } = await pool.query('SELECT id, name, price FROM products WHERE id = $1', [id]);
  return rows[0] || null;
}

async function updateProductPrice(id, price) {
  const { rows } = await pool.query(
    'UPDATE products SET price = $1, updated_at = NOW() WHERE id = $2 RETURNING id, name, price',
    [price, id]
  );
  return rows[0] || null;
}

module.exports = { pool, initSchema, getProductById, updateProductPrice };
