from fastapi import FastAPI, HTTPException, Request, Depends, Form, Header
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional
import sqlite3
import uvicorn
import logging
from werkzeug.security import generate_password_hash, check_password_hash

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db_name = "url_shortener.sqlite"

# Database intilizae and set up the db
def init_db():
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        logger.info("Initializing database tables if not already present.")
        cursor.execute('''CREATE TABLE IF NOT EXISTS URLs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_url TEXT NOT NULL UNIQUE,
            created_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            password TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS AccessLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_url TEXT NOT NULL,
            accessed_at DATETIME NOT NULL,
            ip_address TEXT NOT NULL,
            FOREIGN KEY (short_url) REFERENCES URLs (short_url)
        )''')
        conn.commit()
        logger.info("Database initialized successfully.")

init_db()

# Models
class URLRequest(BaseModel):
    original_url: HttpUrl
    expiry_hours: Optional[int] = 24
    password: Optional[str] = None

class AnalyticsResponse(BaseModel):
    short_url: str
    original_url: str
    created_at: str
    expires_at: str
    access_count: int
    access_logs: list[dict]

 
def generate_short_url(original_url: str) -> str:
    logger.info("Generating short URL for the original URL: %s", original_url)
    return sha256(str(original_url).encode()).hexdigest()[:8]

def get_db_connection():
    logger.info("Establishing database connection.")
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

# Endpoints
@app.post("/shorten")
def shorten_url(request: URLRequest, request_context: Request):
    logger.info("Received request to shorten URL: %s", request.original_url)
    original_url = str(request.original_url)  # Convert HttpUrl to string
    short_url = generate_short_url(original_url)
    expires_at = datetime.now() + timedelta(hours=request.expiry_hours)

    hashed_password = generate_password_hash(request.password) if request.password else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO URLs (original_url, short_url, created_at, expires_at, password) VALUES (?, ?, ?, ?, ?)",
                (original_url, short_url, datetime.now(), expires_at, hashed_password),
            )
            conn.commit()
            logger.info("Short URL created successfully: %s", short_url)
        except sqlite3.IntegrityError:
            logger.warning("Short URL already exists for the provided original URL.")

    host = request_context.client.host
    return {"short_url": f"http://{host}:8000/{short_url}"}

@app.get("/{short_url}", response_class=HTMLResponse)
def redirect_to_url(short_url: str, request: Request):
    logger.info("Received request to redirect short URL: %s", short_url)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM URLs WHERE short_url = ?", (short_url,))
        url_entry = cursor.fetchone()

        if not url_entry:
            logger.error("Short URL not found: %s", short_url)
            raise HTTPException(status_code=404, detail="Short URL not found.")

        if datetime.fromisoformat(url_entry["expires_at"]) < datetime.now():
            logger.warning("Short URL has expired: %s", short_url)
            raise HTTPException(status_code=410, detail="Short URL has expired.")

        if url_entry["password"]:
            # Display password prompt if password is required
            return HTMLResponse(content=f'''
                <!DOCTYPE html>
                <html>
                <body>
                    <h2>This URL is Protected.Password required</h2>
                    <form action="/{short_url}/validate" method="post">
                        <label for="password">Enter Password:</label><br><br>
                        <input type="password" id="password" name="password" required><br><br>
                        <input type="submit" value="Submit">
                    </form>
                </body>
                </html>
            ''')

        # Log access
        cursor.execute(
            "INSERT INTO AccessLogs (short_url, accessed_at, ip_address) VALUES (?, ?, ?)",
            (short_url, datetime.now(), request.client.host),
        )
        conn.commit()
        logger.info("Access logged for short URL: %s", short_url)

    # Redirect to the original URL
    return RedirectResponse(url=url_entry["original_url"])

@app.post("/{short_url}/validate", response_class=HTMLResponse)
def validate_password(short_url: str, password: str = Form(...)):
    logger.info("Validating password for short URL: %s", short_url)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM URLs WHERE short_url = ?", (short_url,))
        url_entry = cursor.fetchone()

        if not url_entry:
            logger.error("Short URL not found: %s", short_url)
            raise HTTPException(status_code=404, detail="Short URL not found.")

        if not check_password_hash(url_entry["password"], password):
            logger.error("Incorrect password for short URL: %s", short_url)
            raise HTTPException(status_code=403, detail="Password is incorrect.")

    # Log access
    cursor.execute(
        "INSERT INTO AccessLogs (short_url, accessed_at, ip_address) VALUES (?, ?, ?)",
        (short_url, datetime.now(), "Validated Access"),
    )
    conn.commit()
    logger.info("Password validated successfully for short URL: %s", short_url)

    # Return an HTML page with auto redirection
    original_url = url_entry["original_url"]
    return HTMLResponse(content=f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Redirecting...</title>
        </head>
        <body>
            <h2>Password validated successfully! Redirecting...</h2>
            <script>
                setTimeout(function() {{
                    window.location.href = "{original_url}";
                }}, 1000);  // Redirect after 1 second
            </script>
        </body>
        </html>
    ''')

@app.post("/analytics/{short_url}/validate", response_class=HTMLResponse)
def validate_analytics_password(short_url: str, password: str = Form(...), request: Request = None):
    logger.info("Validating password for analytics: %s", short_url)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM URLs WHERE short_url = ?", (short_url,))
        url_entry = cursor.fetchone()

        if not url_entry:
            logger.error("Short URL not found for analytics: %s", short_url)
            raise HTTPException(status_code=404, detail="Short URL not found.")

        if not check_password_hash(url_entry["password"], password):
            logger.error("Incorrect password for analytics of short URL: %s", short_url)
            raise HTTPException(status_code=403, detail="Password is incorrect.")

        cursor.execute("SELECT accessed_at, ip_address FROM AccessLogs WHERE short_url = ?", (short_url,))
        logs = cursor.fetchall()

    analytics_data = {
        "short_url": f"http://{request.client.host}:8000/{short_url}",
        "original_url": url_entry["original_url"],
        "created_at": url_entry["created_at"],
        "expires_at": url_entry["expires_at"],
        "access_count": len(logs),
        "access_logs": [{"accessed_at": log["accessed_at"], "ip_address": log["ip_address"]} for log in logs],
    }

    logger.info("Password validated successfully. Fetching analytics for short URL: %s", short_url)
    return HTMLResponse(content=f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analytics</title>
        </head>
        <body>
            <h2>Analytics for Short URL</h2>
            <p><strong>Short URL:</strong> {analytics_data['short_url']}</p>
            <p><strong>Original URL:</strong> {analytics_data['original_url']}</p>
            <p><strong>Created At:</strong> {analytics_data['created_at']}</p>
            <p><strong>Expires At:</strong> {analytics_data['expires_at']}</p>
            <p><strong>Access Count:</strong> {analytics_data['access_count']}</p>
            <h3>Access Logs:</h3>
            <ul>
                {"".join([f"<li>Accessed At: {log['accessed_at']}, IP Address: {log['ip_address']}</li>" for log in analytics_data['access_logs']])}
            </ul>
        </body>
        </html>
    ''')

@app.get("/analytics/{short_url}", response_class=HTMLResponse)
def get_analytics(short_url: str, x_password: Optional[str] = Header(None), request: Request = None):
    logger.info("Received request to fetch analytics for short URL: %s", short_url)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM URLs WHERE short_url = ?", (short_url,))
        url_entry = cursor.fetchone()

        if not url_entry:
            logger.error("Analytics request failed. Short URL not found: %s", short_url)
            raise HTTPException(status_code=404, detail="Short URL not found.")

        if url_entry["password"]:
            if not x_password:
                logger.info("Password required for analytics page.")
                return HTMLResponse(content=f'''
                    <!DOCTYPE html>
                    <html>
                    <body>
                        <h2>Password Required for Analytics</h2>
                        <form action="/analytics/{short_url}/validate" method="post">
                            <label for="password">Enter Password:</label><br><br>
                            <input type="password" id="password" name="password" required><br><br>
                            <input type="submit" value="Submit">
                        </form>
                    </body>
                    </html>
                ''')

            if not check_password_hash(url_entry["password"], x_password):
                logger.error("Incorrect password for analytics of short URL: %s", short_url)
                raise HTTPException(status_code=403, detail="Password is incorrect.")

        cursor.execute("SELECT accessed_at, ip_address FROM AccessLogs WHERE short_url = ?", (short_url,))
        logs = cursor.fetchall()

    analytics_data = {
        "short_url": f"http://{request.client.host}:8000/{short_url}",
        "original_url": url_entry["original_url"],
        "created_at": url_entry["created_at"],
        "expires_at": url_entry["expires_at"],
        "access_count": len(logs),
        "access_logs": [{"accessed_at": log["accessed_at"], "ip_address": log["ip_address"]} for log in logs],
    }

    logger.info("Analytics fetched successfully for short URL: %s", short_url)
    return HTMLResponse(content=f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analytics</title>
        </head>
        <body>
            <h2>Analytics for Short URL</h2>
            <p><strong>Short URL:</strong> {analytics_data['short_url']}</p>
            <p><strong>Original URL:</strong> {analytics_data['original_url']}</p>
            <p><strong>Created At:</strong> {analytics_data['created_at']}</p>
            <p><strong>Expires At:</strong> {analytics_data['expires_at']}</p>
            <p><strong>Access Count:</strong> {analytics_data['access_count']}</p>
            <h3>Access Logs:</h3>
            <ul>
                {"".join([f"<li>Accessed At: {log['accessed_at']}, IP Address: {log['ip_address']}</li>" for log in analytics_data['access_logs']])}
            </ul>
        </body>
        </html>
        ''')

if __name__ == "__main__":
    logger.info("Starting the FastAPI application.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
