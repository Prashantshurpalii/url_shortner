# URL Shortener Service

This project is a FastAPI-based URL shortener service with the following features:

1. Shorten long URLs
2. Set custom expiration times for shortened URLs
3. Password-protect URLs for added security
4. Fetch analytics for shortened URLs (e.g., access count and logs)

---

## Features

### URL Shortening
- Converts long URLs into short, easily shareable links
- Customizable expiration times (default: 24 hours)

### Password Protection
- Option to set password for each shortened URL
- Ensures only authorized users have access to protected URLs

### Analytics
- Provides insights such as:
  - Access count
  - Detailed access logs (timestamp and IP address)
- Analytics pages are also password-protected if the URL is secured

### User Interface
- Password prompts for protected URLs
- Analytics data displayed in a user-friendly HTML format

---

## Getting Started

### Prerequisites
- Python 3.8+
- SQLite
- Pip

### Installation
1. Clone the repository:

   ```bash
   git clone https://github.com/Prashantshurpalii/url_shortner
   cd url_shortner
   ```

2. Create and activate a virtual environment:
   ```bash

   # On Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

5. Access the application at:
   ```
   http://127.0.0.1:8000
   ```

---

## API Endpoints

### 1. Shorten URL
**Endpoint**: `/shorten`  
**Method**: `POST`

#### Request Body
```json
{
  "original_url": "https://www.linkedin.com/pulse/how-install-sqlite-windows-macos-linux-haroon-khan-vtzjf/",
  "expiry_hours": 24,
  "password": "string"
}
```

#### Response
```json
{
  "short_url": "http://127.0.0.1:8000/5020b894"
}
```

---

### 2. Redirect to Original URL
**Endpoint**: `/{short_url}`  
**Method**: `GET`

- If the URL has password then a password box will be displayed to type password.
- On successful validation, the user is redirected to the original URL.

---

### 3. Analytics
**Endpoint**: `/analytics/{short_url}`  
**Method**: `GET`

- Displays analytics data in an HTML format.
- If password exits then a password box will be displayed before analytics are shown.

---

## Project Structure

```
.
├── main.py                 # Main application file
├── requirements.txt        # Dependencies
├── url_shortener.sqlite    # SQLite database
├── README.md               # Project documentation
```

