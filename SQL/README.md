# SQL Learning Plan

> From SQL basics to database architecture and Azure SQL Database

**Timeline:** Weeks 1-6 (parallel with React)  
**Time Commitment:** 4 hours/week  
**Goal:** Write efficient queries and design robust databases

---

## 📋 Learning Path

### Week 1: SQL Fundamentals (4 hours)
**Topics:**
- SELECT basics (columns, WHERE, ORDER BY, LIMIT)
- INSERT, UPDATE, DELETE
- Basic data types
- NULL handling

**Resources:**
- SQLBolt.com (Lessons 1-6)
- W3Schools SQL Tutorial

**Practice:**
```sql
-- Create table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert data
INSERT INTO users (name, email) VALUES 
    ('Alice', 'alice@email.com'),
    ('Bob', 'bob@email.com');

-- Query data
SELECT * FROM users WHERE name LIKE 'A%';
SELECT COUNT(*) FROM users;
```

**Project:** Create users and tasks tables

---

### Week 2: JOINs & Relationships (4 hours)
**Topics:**
- INNER JOIN
- LEFT JOIN, RIGHT JOIN
- Self joins
- Foreign keys
- One-to-many, many-to-many relationships

**Practice:**
```sql
-- Orders and customers
SELECT 
    customers.name,
    orders.order_date,
    SUM(order_items.quantity * order_items.price) as total
FROM orders
JOIN customers ON orders.customer_id = customers.id
JOIN order_items ON orders.id = order_items.order_id
GROUP BY customers.name, orders.order_date;
```

**Project:** Multi-table blog database (users, posts, comments)

---

### Week 3: Aggregations & GROUP BY (4 hours)
**Topics:**
- COUNT, SUM, AVG, MIN, MAX
- GROUP BY
- HAVING clause
- Subqueries

**Practice:**
```sql
-- Sales by category
SELECT 
    category,
    COUNT(*) as product_count,
    AVG(price) as avg_price,
    SUM(stock) as total_stock
FROM products
GROUP BY category
HAVING AVG(price) > 50
ORDER BY avg_price DESC;
```

**Project:** Analytics queries for task manager

---

### Week 4: Database Design (4 hours)
**Topics:**
- ER diagrams
- Normalization (1NF, 2NF, 3NF)
- Primary keys, foreign keys
- Indexes
- Constraints (UNIQUE, CHECK, NOT NULL)

**Practice:**
```sql
-- IT Asset Management schema
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_tag VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    status VARCHAR(50) DEFAULT 'available',
    CHECK (status IN ('available', 'assigned', 'maintenance', 'retired'))
);

CREATE TABLE assignments (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    user_id INTEGER REFERENCES users(id),
    assigned_date DATE NOT NULL,
    returned_date DATE,
    CONSTRAINT valid_dates CHECK (returned_date >= assigned_date)
);

-- Create index for faster lookups
CREATE INDEX idx_asset_tag ON assets(asset_tag);
```

**Project:** Design Project 1 database schema

---

### Week 5: Advanced SQL (4 hours)
**Topics:**
- Views
- Stored procedures
- Triggers
- Window functions
- CTEs (Common Table Expressions)

**Practice:**
```sql
-- Create view for available assets
CREATE VIEW available_assets AS
SELECT a.*, COUNT(asn.id) as total_assignments
FROM assets a
LEFT JOIN assignments asn ON a.id = asn.asset_id
WHERE a.status = 'available'
GROUP BY a.id;

-- Window function for ranking
SELECT 
    name,
    category,
    price,
    RANK() OVER (PARTITION BY category ORDER BY price DESC) as price_rank
FROM products;
```

---

### Week 6: Azure SQL & Performance (4 hours)
**Topics:**
- Azure SQL Database setup
- Connection strings
- Query optimization (EXPLAIN)
- Index strategies
- Transaction management

**Practice:**
```sql
-- Check query performance
EXPLAIN ANALYZE 
SELECT * FROM orders 
WHERE customer_id = 123;

-- Optimize with index
CREATE INDEX idx_customer_orders ON orders(customer_id);

-- Transaction example
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

**Project:** Migrate to Azure SQL, optimize queries

---

## 📚 Resources

**FREE:**
- SQLBolt.com (interactive lessons)
- W3Schools SQL Tutorial
- PostgreSQL Tutorial
- Azure SQL Documentation

**Books:**
- "SQL in 10 Minutes a Day" by Ben Forta
- "Learning SQL" by Alan Beaulieu (3rd Edition)

**Practice:**
- LeetCode SQL problems
- HackerRank SQL challenges
- Your own project databases

---

## ✅ Checklist

- [ ] Week 1: Basic queries mastered
- [ ] Week 2: JOINs comfortable
- [ ] Week 3: Aggregations understood
- [ ] Week 4: Designed multi-table schema
- [ ] Week 5: Used views and stored procedures
- [ ] Week 6: Azure SQL deployed

---

**Master SQL and you'll have a skill for life. Every application needs a database! 💾**