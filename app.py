"""
FastAPI Web Application & REST API Server for Data Scraper
Runs on Port 8001
"""

import os
import sys
import uuid
import threading
import time
from pathlib import Path
from typing import List, Optional

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd
from settings import (
    BASE_DIR,
    OUTPUT_DIR,
    HOST,
    PORT,
    DEFAULT_LINKS
)
from logger import logger
from session_manager import init_scraper_session
from scraper import LeadScraper
from local_scraper import get_maps_driver, scrape_area_leads

app = FastAPI(
    title="Data Scraper B2B & Local Leads Platform",
    description="Web Dashboard and API for extracting business leads across cities & Kolkata locations",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Job Store
JOBS = {}
JOBS_LOCK = threading.Lock()

# Models
class KolkataScrapeRequest(BaseModel):
    category: str = "Real Estate"
    locations: Optional[List[str]] = None
    max_per_location: int = 5

class IndustrialScrapeRequest(BaseModel):
    keyword: str = "Heat Exchangers"
    location: Optional[str] = "Pune"
    max_results: int = 20

class UrlsScrapeRequest(BaseModel):
    urls: List[str]

# Helper to read default locations
def get_default_locations() -> List[str]:
    loc_file = BASE_DIR / "locations.txt"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return [line.strip().strip(',') for line in f if line.strip() and not line.startswith('#')]
    return [
        "Barrackpore", "Sodepur", "Khardah", "Belgharia", "Baguihati", "Dumdum",
        "Birati", "Saltlake", "New Town", "Kaikhali", "Dunlop", "Agarpara",
        "Parkstreet", "Park Circus", "Shakespeare Sarani", "Esplanade"
    ]

# Background Worker for Kolkata Multi-Location Leads
def worker_kolkata_scrape(job_id: str, category: str, locations: List[str], max_per_location: int):
    try:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["message"] = f"Initializing scraper for '{category}' across {len(locations)} locations..."
            JOBS[job_id]["progress"] = 5

        driver = get_maps_driver(headless=True)
        all_leads = []
        total_locs = len(locations)

        try:
            for idx, loc in enumerate(locations, 1):
                progress_pct = int(5 + (idx / total_locs) * 85)
                with JOBS_LOCK:
                    JOBS[job_id]["message"] = f"[{idx}/{total_locs}] Scraping: {loc} for '{category}'..."
                    JOBS[job_id]["progress"] = progress_pct
                    JOBS[job_id]["current_location"] = loc

                leads = scrape_area_leads(driver, category=category, location=loc, city="Kolkata", max_results=max_per_location)
                all_leads.extend(leads)
                
                with JOBS_LOCK:
                    JOBS[job_id]["total_leads"] = len(all_leads)
                    JOBS[job_id]["leads"] = all_leads
                    
                time.sleep(1.0)
        finally:
            driver.quit()

        # Deduplicate & Save Files
        df = pd.DataFrame(all_leads)
        if not df.empty:
            df.drop_duplicates(subset=["Business Name", "Area / Location"], inplace=True)
            
            excel_filename = f"KOLKATA_LEADS_{job_id[:8]}.xlsx"
            csv_filename = f"KOLKATA_LEADS_{job_id[:8]}.csv"
            excel_path = OUTPUT_DIR / excel_filename
            csv_path = OUTPUT_DIR / csv_filename

            # CSV
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")

            # Styled Excel
            try:
                with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name="Leads", index=False)
                    ws = writer.sheets["Leads"]
                    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                    h_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
                    h_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                    border_side = Side(border_style="thin", color="D9D9D9")
                    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
                    
                    for col_idx in range(1, len(df.columns) + 1):
                        cell = ws.cell(row=1, column=col_idx)
                        cell.fill = h_fill
                        cell.font = h_font
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    for col_idx, col_name in enumerate(df.columns, 1):
                        max_len = max(len(col_name), df[col_name].astype(str).str.len().max() if not df.empty else 10)
                        col_letter = ws.cell(row=1, column=col_idx).column_letter
                        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 50)
                    for row in ws.iter_rows(min_row=2, max_row=len(df)+1, min_col=1, max_col=len(df.columns)):
                        for cell in row:
                            cell.border = cell_border
            except Exception:
                df.to_excel(excel_path, index=False)

            with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["message"] = f"Done! {len(df)} leads extracted across Kolkata."
                JOBS[job_id]["excel_file"] = excel_filename
                JOBS[job_id]["csv_file"] = csv_filename
                JOBS[job_id]["leads"] = df.to_dict(orient="records")
                JOBS[job_id]["total_leads"] = len(df)
        else:
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["message"] = "Search finished, but no leads matched."

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["message"] = f"Error: {e}"

# Background Worker for Industrial B2B Portal Leads
def worker_industrial_scrape(job_id: str, keyword: str, location: Optional[str], max_results: int):
    try:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["message"] = "Initializing session with Cloudflare bypass..."
            JOBS[job_id]["progress"] = 10

        session = init_scraper_session(allow_login=False, headless=True)
        scraper = LeadScraper(session)

        with JOBS_LOCK:
            JOBS[job_id]["message"] = f"Searching for '{keyword}'" + (f" in '{location}'" if location else "")
            JOBS[job_id]["progress"] = 25

        results = scraper.search_by_keyword(keyword, location=location, max_results=max_results, enrich_details=True)

        if results:
            df = pd.DataFrame(results)
            excel_filename = f"INDUSTRIAL_LEADS_{job_id[:8]}.xlsx"
            csv_filename = f"INDUSTRIAL_LEADS_{job_id[:8]}.csv"
            excel_path = OUTPUT_DIR / excel_filename
            csv_path = OUTPUT_DIR / csv_filename

            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            df.to_excel(excel_path, index=False)

            with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["message"] = f"Done! {len(df)} industrial leads extracted."
                JOBS[job_id]["excel_file"] = excel_filename
                JOBS[job_id]["csv_file"] = csv_filename
                JOBS[job_id]["leads"] = df.to_dict(orient="records")
                JOBS[job_id]["total_leads"] = len(df)
        else:
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["message"] = "Search completed, but no records found."

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["message"] = f"Error: {e}"

# API Endpoints
@app.get("/api/locations", response_model=List[str])
def api_get_locations():
    """Returns the list of configured Kolkata locations."""
    return get_default_locations()

@app.post("/api/scrape/kolkata")
def api_start_kolkata_scrape(req: KolkataScrapeRequest, bg: BackgroundTasks):
    """Starts a scraping job across Kolkata locations."""
    job_id = str(uuid.uuid4())
    locs = req.locations or get_default_locations()
    
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "type": "kolkata",
            "category": req.category,
            "locations": locs,
            "status": "queued",
            "progress": 0,
            "message": "Scrape request queued...",
            "total_leads": 0,
            "leads": [],
            "excel_file": None,
            "csv_file": None,
            "error": None
        }

    bg.add_task(worker_kolkata_scrape, job_id, req.category, locs, req.max_per_location)
    return {"job_id": job_id, "status": "queued", "message": "Scraping task started in background"}

@app.post("/api/scrape/industrial")
def api_start_industrial_scrape(req: IndustrialScrapeRequest, bg: BackgroundTasks):
    """Starts an industrial portal scraping job."""
    job_id = str(uuid.uuid4())
    
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "type": "industrial",
            "keyword": req.keyword,
            "location": req.location,
            "status": "queued",
            "progress": 0,
            "message": "Scrape request queued...",
            "total_leads": 0,
            "leads": [],
            "excel_file": None,
            "csv_file": None,
            "error": None
        }

    bg.add_task(worker_industrial_scrape, job_id, req.keyword, req.location, req.max_results)
    return {"job_id": job_id, "status": "queued", "message": "Industrial scraping task started in background"}

@app.get("/api/status/{job_id}")
def api_get_status(job_id: str):
    """Checks the status and progress of a scraping job."""
    with JOBS_LOCK:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="Job not found")
        job = JOBS[job_id].copy()
    return job

@app.get("/api/download/excel/{job_id}")
def api_download_excel(job_id: str):
    """Downloads the generated Excel file for a job."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job or not job.get("excel_file"):
            raise HTTPException(status_code=404, detail="Excel file not ready or not found")
        filepath = OUTPUT_DIR / job["excel_file"]
        
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")
    return FileResponse(
        path=filepath,
        filename=job["excel_file"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/download/csv/{job_id}")
def api_download_csv(job_id: str):
    """Downloads the generated CSV file for a job."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job or not job.get("csv_file"):
            raise HTTPException(status_code=404, detail="CSV file not ready or not found")
        filepath = OUTPUT_DIR / job["csv_file"]
        
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")
    return FileResponse(
        path=filepath,
        filename=job["csv_file"],
        media_type="text/csv"
    )

# Frontend Web Dashboard (HTML + CSS + JavaScript)
@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B2B & Local Leads Scraper Dashboard (Port 8001)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-header { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
        .tab-btn.active { border-bottom: 3px solid #2563eb; color: #1d4ed8; font-weight: 700; }
        .spinner { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col font-sans">

    <!-- Top Navigation Bar -->
    <header class="gradient-header text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 py-4 flex flex-col sm:flex-row justify-between items-center gap-3">
            <div class="flex items-center space-x-3">
                <i class="fa-solid fa-satellite-dish text-2xl text-yellow-300"></i>
                <div>
                    <h1 class="text-xl font-bold tracking-tight">LeadPulse Pro — Data Scraper Dashboard</h1>
                    <p class="text-xs text-blue-100">Live Server running on Port 8001 | B2B & Hyper-Local Leads</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-green-500 text-white">
                    <span class="w-2 h-2 mr-1.5 bg-white rounded-full animate-ping"></span> Live Port: 8001
                </span>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full">

        <!-- Navigation Tabs -->
        <div class="flex border-b border-gray-200 mb-6 bg-white rounded-t-lg shadow-sm">
            <button onclick="switchTab('kolkata')" id="tab-btn-kolkata" class="tab-btn active px-6 py-3.5 text-sm font-medium text-gray-600 hover:text-blue-600 flex items-center gap-2">
                <i class="fa-solid fa-location-dot text-red-500"></i> Kolkata Multi-Location Leads (16 Areas)
            </button>
            <button onclick="switchTab('industrial')" id="tab-btn-industrial" class="tab-btn px-6 py-3.5 text-sm font-medium text-gray-600 hover:text-blue-600 flex items-center gap-2">
                <i class="fa-solid fa-industry text-blue-600"></i> Industrial B2B Portal Scraper
            </button>
        </div>

        <!-- TAB 1: Kolkata Multi-Location Leads -->
        <div id="tab-kolkata" class="tab-content">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Controls Column -->
                <div class="lg:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between">
                    <div>
                        <h2 class="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <i class="fa-solid fa-sliders text-blue-600"></i> Search Parameters
                        </h2>

                        <!-- Business Category -->
                        <div class="mb-4">
                            <label class="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                                Business Category / Keyword <span class="text-red-500">*</span>
                            </label>
                            <input type="text" id="k-category" value="Real Estate" placeholder="e.g. Real Estate, Doctors, IT Companies, Hardware"
                                   class="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                            <p class="text-xs text-gray-400 mt-1">Example: Doctors, Cafes, Interior Designers, Traders</p>
                        </div>

                        <!-- Max leads per area -->
                        <div class="mb-5">
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-semibold text-gray-700 uppercase tracking-wider">Leads Per Location</label>
                                <span id="k-max-label" class="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">5</span>
                            </div>
                            <input type="range" id="k-max" min="1" max="20" value="5" oninput="document.getElementById('k-max-label').innerText = this.value"
                                   class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600">
                        </div>

                        <!-- Locations selection -->
                        <div class="mb-5">
                            <div class="flex justify-between items-center mb-2">
                                <label class="text-xs font-semibold text-gray-700 uppercase tracking-wider">Target Locations (16)</label>
                                <div class="space-x-1 text-xs">
                                    <button type="button" onclick="toggleAllLocations(true)" class="text-blue-600 hover:underline">All</button>
                                    <span class="text-gray-300">|</span>
                                    <button type="button" onclick="toggleAllLocations(false)" class="text-gray-500 hover:underline">Clear</button>
                                </div>
                            </div>
                            <div id="locations-checkboxes" class="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-xs">
                                <!-- Populated dynamically by JS -->
                            </div>
                        </div>
                    </div>

                    <button onclick="startKolkataScrape()" id="k-start-btn" class="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition flex items-center justify-center gap-2">
                        <i class="fa-solid fa-play"></i> Start Extracting Leads
                    </button>
                </div>

                <!-- Live Status & Results Column -->
                <div class="lg:col-span-2 space-y-6">
                    <!-- Progress Card -->
                    <div id="status-card" class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hidden">
                        <div class="flex justify-between items-center mb-2">
                            <span id="status-badge" class="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
                                Running
                            </span>
                            <span id="status-percent" class="text-sm font-extrabold text-blue-600">0%</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2.5 mb-3 overflow-hidden">
                            <div id="progress-bar" class="bg-blue-600 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                        <p id="status-message" class="text-xs text-gray-600 flex items-center gap-2">
                            <i class="fa-solid fa-circle-notch spinner text-blue-600"></i> Processing...
                        </p>

                        <!-- Download Action Buttons (Appears when completed) -->
                        <div id="download-actions" class="mt-4 pt-4 border-t border-gray-100 flex flex-wrap gap-3 hidden">
                            <a id="btn-download-excel" href="#" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow flex items-center gap-1.5 transition">
                                <i class="fa-solid fa-file-excel"></i> Download Excel (.xlsx)
                            </a>
                            <a id="btn-download-csv" href="#" class="px-4 py-2 bg-gray-800 hover:bg-gray-900 text-white rounded-lg text-xs font-bold shadow flex items-center gap-1.5 transition">
                                <i class="fa-solid fa-file-csv"></i> Download CSV (.csv)
                            </a>
                        </div>
                    </div>

                    <!-- Results Table Preview -->
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4">
                            <h3 class="text-base font-bold text-gray-900 flex items-center gap-2">
                                <i class="fa-solid fa-table-list text-gray-600"></i> Extracted Leads Table
                                <span id="leads-counter" class="text-xs font-normal bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">0 leads</span>
                            </h3>
                            <input type="text" id="table-filter" onkeyup="filterTable()" placeholder="Quick filter..." class="text-xs px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500">
                        </div>

                        <div class="overflow-x-auto max-h-96 border border-gray-200 rounded-lg">
                            <table class="min-w-full divide-y divide-gray-200 text-xs">
                                <thead class="bg-gray-100 sticky top-0">
                                    <tr>
                                        <th class="px-3 py-2.5 text-left font-semibold text-gray-700">Business Name</th>
                                        <th class="px-3 py-2.5 text-left font-semibold text-gray-700">Area / Location</th>
                                        <th class="px-3 py-2.5 text-left font-semibold text-gray-700">Phone Number</th>
                                        <th class="px-3 py-2.5 text-left font-semibold text-gray-700">Rating</th>
                                        <th class="px-3 py-2.5 text-left font-semibold text-gray-700">Website</th>
                                    </tr>
                                </thead>
                                <tbody id="leads-tbody" class="bg-white divide-y divide-gray-200">
                                    <tr>
                                        <td colspan="5" class="px-4 py-8 text-center text-gray-400">
                                            No leads extracted yet. Configure parameters and click "Start Extracting Leads".
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: Industrial B2B Portal Scraper -->
        <div id="tab-industrial" class="tab-content hidden">
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 max-w-xl mx-auto">
                <h2 class="text-lg font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <i class="fa-solid fa-industry text-blue-600"></i> Maharashtra Directory Industrial B2B Search
                </h2>
                <p class="text-xs text-gray-500 mb-5">Scrape verified industrial manufacturers, exporters, directors, and factory contact details.</p>

                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Product / Keyword</label>
                        <input type="text" id="i-keyword" value="Heat Exchangers" placeholder="e.g. Heat Exchangers, Boilers, Valves" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">City / Region (Optional)</label>
                        <input type="text" id="i-location" value="Pune" placeholder="e.g. Pune, Mumbai, Thane" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Max Results</label>
                        <input type="number" id="i-max" value="20" min="5" max="100" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                    </div>
                    <button onclick="startIndustrialScrape()" id="i-start-btn" class="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-md transition flex items-center justify-center gap-2">
                        <i class="fa-solid fa-magnifying-glass"></i> Search Industrial Leads
                    </button>
                </div>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-500">
        Data Scraper Engine v2.0 &bull; Running on <strong>http://localhost:8001</strong> &bull; Styled Excel & CSV Ready
    </footer>

    <!-- JavaScript Logic -->
    <script>
        const DEFAULT_LOCATIONS = [
            "Barrackpore", "Sodepur", "Khardah", "Belgharia", "Baguihati", "Dumdum",
            "Birati", "Saltlake", "New Town", "Kaikhali", "Dunlop", "Agarpara",
            "Parkstreet", "Park Circus", "Shakespeare Sarani", "Esplanade"
        ];

        let activeJobId = null;
        let pollTimer = null;
        let currentLeads = [];

        // Populate Location Checkboxes
        function populateLocations() {
            const container = document.getElementById('locations-checkboxes');
            container.innerHTML = '';
            DEFAULT_LOCATIONS.forEach(loc => {
                const label = document.createElement('label');
                label.className = 'flex items-center space-x-1.5 cursor-pointer';
                label.innerHTML = `
                    <input type="checkbox" name="loc" value="${loc}" checked class="rounded text-blue-600 focus:ring-0">
                    <span class="truncate">${loc}</span>
                `;
                container.appendChild(label);
            });
        }

        function toggleAllLocations(check) {
            document.querySelectorAll('input[name="loc"]').forEach(cb => cb.checked = check);
        }

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));

            if (tab === 'kolkata') {
                document.getElementById('tab-btn-kolkata').classList.add('active');
                document.getElementById('tab-kolkata').classList.remove('hidden');
            } else {
                document.getElementById('tab-btn-industrial').classList.add('active');
                document.getElementById('tab-industrial').classList.remove('hidden');
            }
        }

        // Start Kolkata Scraping
        async function startKolkataScrape() {
            const category = document.getElementById('k-category').value.trim();
            if (!category) {
                alert('Please enter a business category (e.g. Real Estate, Doctors)!');
                return;
            }

            const checkedLocs = Array.from(document.querySelectorAll('input[name="loc"]:checked')).map(cb => cb.value);
            if (checkedLocs.length === 0) {
                alert('Please select at least one location!');
                return;
            }

            const maxPerLoc = parseInt(document.getElementById('k-max').value) || 5;

            // UI state
            document.getElementById('k-start-btn').disabled = true;
            document.getElementById('status-card').classList.remove('hidden');
            document.getElementById('download-actions').classList.add('hidden');
            updateStatusUI("Starting scraper...", 5, "running");

            try {
                const res = await fetch('/api/scrape/kolkata', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        category: category,
                        locations: checkedLocs,
                        max_per_location: maxPerLoc
                    })
                });
                const data = await res.json();
                activeJobId = data.job_id;
                startPolling(activeJobId);
            } catch (err) {
                alert('Failed to start scrape: ' + err);
                document.getElementById('k-start-btn').disabled = false;
            }
        }

        // Start Industrial Scraping
        async function startIndustrialScrape() {
            const kw = document.getElementById('i-keyword').value.trim();
            const loc = document.getElementById('i-location').value.trim();
            const maxR = parseInt(document.getElementById('i-max').value) || 20;

            if (!kw) {
                alert('Please enter a product or keyword!');
                return;
            }

            switchTab('kolkata'); // Switch to main tab to view progress card & table
            document.getElementById('status-card').classList.remove('hidden');
            document.getElementById('download-actions').classList.add('hidden');
            updateStatusUI("Starting industrial scraper...", 5, "running");

            try {
                const res = await fetch('/api/scrape/industrial', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        keyword: kw,
                        location: loc,
                        max_results: maxR
                    })
                });
                const data = await res.json();
                activeJobId = data.job_id;
                startPolling(activeJobId);
            } catch (err) {
                alert('Failed: ' + err);
            }
        }

        // Polling loop
        function startPolling(jobId) {
            if (pollTimer) clearInterval(pollTimer);

            pollTimer = setInterval(async () => {
                try {
                    const res = await fetch(`/api/status/${jobId}`);
                    const job = await res.json();

                    updateStatusUI(job.message, job.progress, job.status);

                    if (job.leads && job.leads.length > 0) {
                        currentLeads = job.leads;
                        renderTable(job.leads);
                    }

                    if (job.status === 'completed' || job.status === 'failed') {
                        clearInterval(pollTimer);
                        document.getElementById('k-start-btn').disabled = false;

                        if (job.status === 'completed' && job.excel_file) {
                            document.getElementById('download-actions').classList.remove('hidden');
                            document.getElementById('btn-download-excel').href = `/api/download/excel/${jobId}`;
                            document.getElementById('btn-download-csv').href = `/api/download/csv/${jobId}`;
                        }
                    }
                } catch (e) {
                    console.error("Polling error", e);
                }
            }, 1500);
        }

        function updateStatusUI(message, progress, status) {
            document.getElementById('status-message').innerHTML = `
                <i class="fa-solid ${status === 'running' ? 'fa-circle-notch spinner' : (status === 'completed' ? 'fa-check text-green-600' : 'fa-triangle-exclamation text-red-500')}"></i>
                ${message}
            `;
            document.getElementById('progress-bar').style.width = `${progress}%`;
            document.getElementById('status-percent').innerText = `${progress}%`;

            const badge = document.getElementById('status-badge');
            badge.innerText = status;
            if (status === 'completed') {
                badge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-green-100 text-green-800';
            } else if (status === 'failed') {
                badge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-100 text-red-800';
            } else {
                badge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800';
            }
        }

        function renderTable(leads) {
            const tbody = document.getElementById('leads-tbody');
            document.getElementById('leads-counter').innerText = `${leads.length} leads`;
            tbody.innerHTML = '';

            leads.forEach(l => {
                const name = l["Business Name"] || l["Company Name"] || "-";
                const loc = l["Area / Location"] || l["City / Locality"] || "-";
                const phone = l["Phone Number"] || l["Phone / Contact Info"] || "-";
                const rating = l["Rating"] ? `⭐ ${l["Rating"]} (${l["Review Count"] || 0})` : "-";
                const website = l["Website"] ? `<a href="${l["Website"]}" target="_blank" class="text-blue-600 hover:underline">Visit</a>` : "-";

                const tr = document.createElement('tr');
                tr.className = "hover:bg-gray-50";
                tr.innerHTML = `
                    <td class="px-3 py-2 font-medium text-gray-900">${name}</td>
                    <td class="px-3 py-2 text-gray-600">${loc}</td>
                    <td class="px-3 py-2 font-mono text-xs ${phone.includes('0') || phone.includes('+') ? 'text-green-700 font-semibold' : 'text-gray-500'}">${phone}</td>
                    <td class="px-3 py-2 text-gray-600">${rating}</td>
                    <td class="px-3 py-2">${website}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function filterTable() {
            const q = document.getElementById('table-filter').value.toLowerCase();
            const filtered = currentLeads.filter(l => {
                const str = Object.values(l).join(' ').toLowerCase();
                return str.includes(q);
            });
            renderTable(filtered);
        }

        // Initialize on load
        window.onload = populateLocations;
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    import uvicorn
    print(f"\n" + "="*70)
    print(f"🚀 LeadPulse Pro Web App running on: http://localhost:{PORT}")
    print(f"📡 Network URL: http://0.0.0.0:{PORT}")
    print(f"="*70 + "\n")
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)

