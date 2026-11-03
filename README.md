# 🚀 B2B & Local Business Lead Data Scraper Platform

A production-ready, high-performance web scraper & live web dashboard running on **Port 8001** for extracting B2B and hyper-local business leads across targeted cities, industrial zones, and micro-locations.

---

## 🌐 Live Web Dashboard (Port 8001)

You can access the full interactive web application by opening:
👉 **[http://localhost:8001](http://localhost:8001)**

### Web Dashboard Features:
- **Interactive Location Selector**: Check/uncheck any of the 16 Kolkata locations (Barrackpore, Salt Lake, Park Street, New Town, etc.).
- **Live Real-Time Progress Bar**: Live progress tracking and status messages while scraping in the background.
- **Interactive Leads Table**: Real-time table view with search filter and clickable links.
- **1-Click Export**: Instant download buttons for **Excel (.xlsx)** and **CSV (.csv)**.

---

## 📁 Project Structure

```
d:\DataScrapper\
│
├── .env                  # Environment config (PORT=8001, HOST=0.0.0.0)
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── settings.py           # Configuration manager
├── logger.py             # Dual console & rotating file logging
├── app.py                # FastAPI Web Server & REST API (Port 8001)
├── session_manager.py    # Cloudflare bypass & anti-bot handshake
├── scraper.py            # B2B industrial portal scraping engine
├── local_scraper.py      # Multi-Location Hyper-Local Places scraper engine
├── exporter.py           # Styled Excel & CSV export logic
├── main.py               # CLI runner & Interactive Menu
├── locations.txt         # Pre-configured 16 Kolkata locations
├── run_server.bat        # 1-Click launcher for Web Server (Port 8001)
├── run.bat               # 1-Click launcher for CLI Menu
├── requirements.txt      # Production dependencies
│
├── exports/              # Auto-created output directory for Excel & CSV
└── logs/                 # Auto-created output directory for logs
```

---

## 🚀 How to Run on Port 8001

### Option 1: Double-Click Launcher (Windows)
Double-click **`run_server.bat`** in `D:\DataScrapper`.
The web server will start and be accessible at `http://localhost:8001`.

### Option 2: Terminal Command
```bash
python app.py
```
Or with Uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8001
```

---

## 📡 REST API Documentation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the Web Dashboard UI |
| `GET` | `/api/locations` | Returns list of configured Kolkata locations |
| `POST` | `/api/scrape/kolkata` | Starts background scrape across Kolkata locations |
| `POST` | `/api/scrape/industrial` | Starts industrial B2B portal scraping job |
| `GET` | `/api/status/{job_id}` | Returns current progress (0-100%), status & leads |
| `GET` | `/api/download/excel/{job_id}` | Downloads styled Excel (.xlsx) file |
| `GET` | `/api/download/csv/{job_id}` | Downloads CSV (.csv) file |
