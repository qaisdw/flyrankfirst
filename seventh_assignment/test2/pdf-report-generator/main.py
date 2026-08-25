from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
import sqlite3
from datetime import datetime
import os
from playwright.async_api import async_playwright

app = FastAPI()

# Ensure the reports artifact directory exists
os.makedirs('reports', exist_ok=True)

def get_db():
    conn = sqlite3.connect('report.db')
    conn.row_factory = sqlite3.Row
    return conn

# STAGE 0: Setup Ready Checkpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# STAGE 2: Aggregation Queries
def get_report_data():
    conn = get_db()
    cursor = conn.cursor()

    # Total number of orders
    cursor.execute('SELECT COUNT(*) as total_orders FROM orders')
    total_orders = cursor.fetchone()['total_orders']

    # Total revenue
    cursor.execute('SELECT SUM(amount) as total_revenue FROM orders')
    total_revenue = cursor.fetchone()['total_revenue'] or 0

    # Top 5 products by revenue
    cursor.execute('''
        SELECT product, SUM(amount) as revenue
        FROM orders
        GROUP BY product
        ORDER BY revenue DESC
        LIMIT 5
    ''')
    top_products = [dict(row) for row in cursor.fetchall()]

    # Orders per day for the last 7 days
    cursor.execute('''
        SELECT created_at, COUNT(*) as daily_orders
        FROM orders
        WHERE created_at >= date('now', '-7 days')
        GROUP BY created_at
        ORDER BY created_at
    ''')
    daily_orders = [dict(row) for row in cursor.fetchall()]

    # All orders (long table to test page breaks)
    cursor.execute('SELECT * FROM orders ORDER BY created_at DESC')
    all_orders = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "top_products": top_products,
        "daily_orders": daily_orders,
        "all_orders": all_orders,
        "date": datetime.now().strftime('%Y-%m-%d')
    }

# STAGE 3: HTML to PDF Rendering
async def generate_pdf(data, filepath):
    # HTML Template with print CSS for clean page breaks
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1, h2 {{ color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background-color: #f4f4f4; }}
            
            /* Stage 3 Fixes: Repeat headers and avoid slicing rows */
            thead {{ display: table-header-group; }}
            tr {{ page-break-inside: avoid; break-inside: avoid; }}
        </style>
    </head>
    <body>
        <h1>Shop Sales Report - {data['date']}</h1>
        <h2>Summary</h2>
        <p><strong>Total Orders:</strong> {data['total_orders']}</p>
        <p><strong>Total Revenue:</strong> ${data['total_revenue']}</p>

        <h2>Top 5 Products by Revenue</h2>
        <table>
            <thead>
                <tr><th>Product</th><th>Revenue</th></tr>
            </thead>
            <tbody>
                {"".join(f"<tr><td>{p['product']}</td><td>${round(p['revenue'], 2)}</td></tr>" for p in data['top_products'])}
            </tbody>
        </table>

        <h2>All Orders</h2>
        <table>
            <thead>
                <tr><th>ID</th><th>Customer</th><th>Product</th><th>Amount</th><th>Date</th></tr>
            </thead>
            <tbody>
                {"".join(f"<tr><td>{o['id']}</td><td>{o['customer']}</td><td>{o['product']}</td><td>${round(o['amount'], 2)}</td><td>{o['created_at']}</td></tr>" for o in data['all_orders'])}
            </tbody>
        </table>
    </body>
    </html>
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)
        await page.pdf(path=filepath, format="A4", print_background=True)
        await browser.close()

# STAGE 4 & 5: Generate and serve by link / Ask twice, get one
@app.post("/reports", status_code=201)
async def create_report(response: Response, force: bool = False):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()

    # Stage 5 Idempotency: Same request twice -> one effect, one file.
    if not force:
        cursor.execute('SELECT id, path FROM reports WHERE created_at = ?', (today,))
        existing_report = cursor.fetchone()
        if existing_report:
            conn.close()
            response.status_code = 200 # Return 200 instead of 201 for existing
            return {
                "id": existing_report['id'],
                "file": f"/reports/{existing_report['id']}/file"
            }

    # Generate new report data
    data = get_report_data()
    
    # Insert placeholder row to get an ID
    cursor.execute('INSERT INTO reports (path, created_at) VALUES (?, ?)', ('temp', today))
    report_id = cursor.lastrowid
    
    # Render PDF to disk
    filepath = f"reports/{report_id}.pdf"
    await generate_pdf(data, filepath)
    
    # Update row with actual path
    cursor.execute('UPDATE reports SET path = ? WHERE id = ?', (filepath, report_id))
    conn.commit()
    conn.close()

    return {
        "id": report_id,
        "file": f"/reports/{report_id}/file"
    }

@app.get("/reports/{report_id}")
def get_report(report_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
    report = cursor.fetchone()
    conn.close()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return {
        "id": report['id'],
        "created_at": report['created_at'],
        "file": f"/reports/{report['id']}/file"
    }

@app.get("/reports/{report_id}/file")
def download_report(report_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT path FROM reports WHERE id = ?', (report_id,))
    report = cursor.fetchone()
    conn.close()
    
    if not report or not os.path.exists(report['path']):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Store and link: Only this endpoint moves the megabytes
    return FileResponse(report['path'], media_type='application/pdf', filename=f"report_{report_id}.pdf")