# PDF Report Generator

This is a complete data-to-document backend pipeline built with Python, FastAPI, SQLite, and Playwright. It utilizes the "Option A - The little shop" dataset.

## How to run it
1. Install dependencies: `pip install fastapi uvicorn playwright && playwright install chromium`
2. Seed the database: `python seed.py`
3. Run the API: `uvicorn main:app --reload`
4. Generate report (creates a visible pause): `curl -i -X POST http://localhost:8000/reports`
5. Download the file: `curl -o my-report.pdf http://localhost:8000/reports/1/file`

## Aggregation SQL Used
```sql
-- Total orders
SELECT COUNT(*) as total_orders FROM orders;

-- Total revenue
SELECT SUM(amount) as total_revenue FROM orders;

-- Top 5 products
SELECT product, SUM(amount) as revenue
FROM orders GROUP BY product ORDER BY revenue DESC LIMIT 5;

-- Orders per day (last 7 days)
SELECT created_at, COUNT(*) as daily_orders
FROM orders WHERE created_at >= date('now', '-7 days') GROUP BY created_at ORDER BY created_at;