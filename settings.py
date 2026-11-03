"""
Settings Module
Loads configuration from .env with fallback defaults for live/production deployment.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "t", "yes", "y")

def _get_int(key: str, default: int = 20) -> int:
    val = os.getenv(key)
    try:
        return int(val) if val else default
    except ValueError:
        return default

def _get_float(key: str, default: float = 1.0) -> float:
    val = os.getenv(key)
    try:
        return float(val) if val else default
    except ValueError:
        return default

# Browser & Scraping Settings
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = _get_int("PORT", default=8000)

HEADLESS_MODE: bool = _get_bool("HEADLESS_MODE", default=False)
REQUEST_DELAY_MIN: float = _get_float("REQUEST_DELAY_MIN", default=0.5)
REQUEST_DELAY_MAX: float = _get_float("REQUEST_DELAY_MAX", default=1.5)
PAGE_TIMEOUT: int = _get_int("PAGE_TIMEOUT", default=20)
MAX_RETRIES: int = _get_int("MAX_RETRIES", default=3)

# Output Paths
OUTPUT_DIR_NAME: str = os.getenv("OUTPUT_DIR", "./exports")
OUTPUT_DIR: Path = (BASE_DIR / OUTPUT_DIR_NAME).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_FILENAME: str = os.getenv("EXCEL_FILENAME", "FINAL_FULL_DATA.xlsx")
CSV_FILENAME: str = os.getenv("CSV_FILENAME", "FINAL_FULL_DATA.csv")

EXCEL_OUTPUT_PATH: Path = OUTPUT_DIR / EXCEL_FILENAME
CSV_OUTPUT_PATH: Path = OUTPUT_DIR / CSV_FILENAME

# Logging Settings
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE_NAME: str = os.getenv("LOG_FILE", "./logs/scraper.log")
LOG_FILE_PATH: Path = (BASE_DIR / LOG_FILE_NAME).resolve()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Advanced Network Settings
USER_AGENT: str = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PROXY_URL: str = os.getenv("PROXY_URL", "").strip() or None

# Website Targets
BASE_URL: str = "https://www.maharashtradirectory.com"
SEARCH_URL: str = "https://www.maharashtradirectory.com/Search/Search"

# Target Data Schema
DATA_COLUMNS = [
    "Company Name",
    "Contact Person / Lead",
    "City / Locality",
    "State",
    "Pincode",
    "Full Address",
    "Phone / Contact Info",
    "Website",
    "Description",
    "Profile Link"
]

# Default starting URLs
DEFAULT_LINKS = [
    'https://www.maharashtradirectory.com/companyinfo/chintamani-thermal-technologies-pvtltd-pune-1725.html',
    'https://www.maharashtradirectory.com/companyinfo/thermotech-industries-india-pvtltd-thane-19727.html',
    'https://www.maharashtradirectory.com/companyinfo/akshay-engineering-works-pune-92504.html',
    'https://www.maharashtradirectory.com/companyinfo/heft-engineers-pvtltd-palghar-124770.html',
    'https://www.maharashtradirectory.com/companyinfo/tube-tech-copper-and-alloys-pvtltd-palghar-109746.html',
    'https://www.maharashtradirectory.com/companyinfo/fin-tubes-mfgco-navi-mumbai-2641.html',
    'https://www.maharashtradirectory.com/companyinfo/shiraz-group-pune-160504.html',
    'https://www.maharashtradirectory.com/companyinfo/tpp-boilers-pvtltd-mumbai-33671.html',
    'https://www.maharashtradirectory.com/companyinfo/visoka-engineering-chennai-43509.html',
    'https://www.maharashtradirectory.com/companyinfo/trust-well-engineers-india-pvtltd-pune-107647.html',
    'https://www.maharashtradirectory.com/companyinfo/mercure-metals-and-alloys-pvtltd-mumbai-152621.html',
    'https://www.maharashtradirectory.com/companyinfo/abe-and-hex-india-pvtltd-ghaziabad-154644.html',
    'https://www.maharashtradirectory.com/companyinfo/prime-fin-tubes-mumbai-138575.html',
    'https://www.maharashtradirectory.com/companyinfo/excel-coolers-coimbatore-132785.html'
]

