"""
Main Entry Point for Data Scraper
Interactive CLI and script runner configured via settings.py and .env
"""

import sys
# Ensure console handles UTF-8 cleanly on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import argparse
import os
from settings import (
    DEFAULT_LINKS,
    EXCEL_OUTPUT_PATH,
    CSV_OUTPUT_PATH,
    HEADLESS_MODE
)
from logger import logger
from session_manager import init_scraper_session
from scraper import LeadScraper
from exporter import export_data
from local_scraper import run_multi_location_scraper

def banner():
    print("""
===============================================================
       🚀 MAHARASHTRA DIRECTORY B2B LEAD DATA SCRAPER 🚀       
===============================================================
  Extract: Company Name | Contact Person / Lead | Address
           City & Pincode | Phone Numbers | Website | Details
===============================================================
""")

def run_scraper_flow(links_to_scrape=None, keyword=None, location=None, allow_login=False, max_results=50, headless=None):
    """Executes the end-to-end scraping workflow."""
    # Step 1: Initialize Session with Cloudflare bypass
    session = init_scraper_session(allow_login=allow_login, headless=headless)
    scraper = LeadScraper(session)

    # Step 2: Scrape based on mode
    results = []
    if keyword:
        results = scraper.search_by_keyword(keyword, location=location, max_results=max_results, enrich_details=True)
    elif links_to_scrape:
        results = scraper.scrape_links_list(links_to_scrape)
    else:
        logger.error("No links or keyword specified!")
        return

    # Step 3: Export Data
    if results:
        df = export_data(results, excel_path=EXCEL_OUTPUT_PATH, csv_path=CSV_OUTPUT_PATH)
        print("\n📋 PREVIEW OF EXTRACTED LEADS:")
        print("="*75)
        display_cols = [c for c in ["Company Name", "Contact Person / Lead", "City / Locality", "Pincode"] if c in df.columns]
        print(df[display_cols].head(10).to_string(index=False))
        print("="*75)
        print(f"\n📁 Files generated in:")
        print(f"   1. {EXCEL_OUTPUT_PATH}")
        print(f"   2. {CSV_OUTPUT_PATH}")
    else:
        logger.warning("No data was extracted.")

def interactive_menu():
    banner()
    print("CHOOSE SCRAPING MODE:")
    print(" [1] Scrape Default 14 Company Links (Jo tumne provide kiye)")
    print(" [2] Search by Keyword & Location (e.g. 'Heat Exchangers' in 'Pune')")
    print(" [3] Enter custom Category URL or Search URL directly")
    print(" [4] Load URLs from 'urls.txt' file")
    print(" [5] Multi-Location Kolkata Leads (Barrackpore, Sodepur, Saltlake, etc.)")
    print(" [6] Exit")
    print("-" * 63)

    try:
        choice = input("👉 Enter choice (1-6) [Default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if not choice:
        choice = "1"

    if choice == "1":
        print(f"\nSelected: Scrape {len(DEFAULT_LINKS)} Default Links")
        allow_login = ask_login_pref()
        run_scraper_flow(links_to_scrape=DEFAULT_LINKS, allow_login=allow_login)

    elif choice == "2":
        try:
            kw = input("👉 Enter Product/Keyword (e.g. Heat Exchangers / Boilers / Valves): ").strip()
        except EOFError:
            kw = "Heat Exchangers"
        if not kw:
            kw = "Heat Exchangers"
            
        try:
            loc = input("👉 Enter Location/City (Optional, e.g. Pune / Mumbai / Thane - Leave blank for all): ").strip()
        except EOFError:
            loc = None
        if not loc:
            loc = None

        try:
            max_r = input("👉 Max results to extract [Default: 30]: ").strip()
            max_r = int(max_r) if max_r.isdigit() else 30
        except EOFError:
            max_r = 30

        allow_login = ask_login_pref()
        run_scraper_flow(keyword=kw, location=loc, allow_login=allow_login, max_results=max_r)

    elif choice == "3":
        try:
            url = input("👉 Paste Maharashtra Directory URL: ").strip()
        except EOFError:
            url = ""
        if url:
            allow_login = ask_login_pref()
            if "companyinfo" in url:
                run_scraper_flow(links_to_scrape=[url], allow_login=allow_login)
            else:
                session = init_scraper_session(allow_login=allow_login)
                scraper = LeadScraper(session)
                resp = session.get(url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = []
                for a in soup.find_all('a', href=True):
                    if '/companyinfo/' in a['href']:
                        full = a['href'] if a['href'].startswith('http') else "https://www.maharashtradirectory.com" + a['href']
                        if full not in links:
                            links.append(full)
                print(f"Found {len(links)} company links from page.")
                results = scraper.scrape_links_list(links[:30])
                export_data(results)

    elif choice == "4":
        txt_path = "urls.txt"
        if not os.path.exists(txt_path):
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(DEFAULT_LINKS))
            print(f"Created sample '{txt_path}' with default links. Add your URLs there and run again.")
            urls = DEFAULT_LINKS
        else:
            with open(txt_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]
            print(f"Loaded {len(urls)} URLs from '{txt_path}'.")

        allow_login = ask_login_pref()
        run_scraper_flow(links_to_scrape=urls, allow_login=allow_login)

    elif choice == "5":
        print("\n=== Kolkata Multi-Location Leads Scraper ===")
        try:
            cat = input("👉 Enter Business Category/Keyword (e.g. Real Estate, Doctors, IT Companies, Restaurants) [Default: Real Estate]: ").strip()
        except EOFError:
            cat = "Real Estate"
        if not cat:
            cat = "Real Estate"

        try:
            max_p = input("👉 Max leads per location [Default: 5]: ").strip()
            max_p = int(max_p) if max_p.isdigit() else 5
        except EOFError:
            max_p = 5

        run_multi_location_scraper(category=cat, locations_file="locations.txt", max_per_location=max_p)

    elif choice == "6":
        print("Goodbye!")
        return

def ask_login_pref():
    try:
        ans = input("👉 Kya aap phone numbers unmask karne ke liye Chrome me OTP login karna chahte hain? (y/N): ").strip().lower()
        return ans in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        return False

def parse_cli():
    parser = argparse.ArgumentParser(description="Maharashtra Directory B2B Lead Scraper")
    parser.add_argument("--mode", choices=["default", "search", "file", "interactive"], default="interactive",
                        help="Scraping mode to execute")
    parser.add_argument("--keyword", type=str, help="Keyword/Product to search")
    parser.add_argument("--location", type=str, help="Location/City filter (e.g. Pune, Mumbai)")
    parser.add_argument("--max", type=int, default=30, help="Maximum results to scrape")
    parser.add_argument("--file", type=str, default="urls.txt", help="Path to file containing URLs")
    parser.add_argument("--login", action="store_true", help="Pause to allow user OTP login in Chrome")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--kolkata", action="store_true", help="Run multi-location scraper for Kolkata locations")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_cli()

    headless_opt = True if args.headless else None

    if args.kolkata:
        kw = args.keyword or "Real Estate"
        run_multi_location_scraper(category=kw, locations_file="locations.txt", max_per_location=args.max or 5)
    elif args.mode == "default" or (args.mode == "interactive" and len(sys.argv) > 1 and not args.keyword):
        run_scraper_flow(links_to_scrape=DEFAULT_LINKS, allow_login=args.login, headless=headless_opt)
    elif args.keyword or args.mode == "search":
        kw = args.keyword or "Heat Exchangers"
        run_scraper_flow(keyword=kw, location=args.location, allow_login=args.login, max_results=args.max, headless=headless_opt)
    elif args.mode == "file":
        urls = []
        if os.path.exists(args.file):
            with open(args.file, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]
        else:
            urls = DEFAULT_LINKS
        run_scraper_flow(links_to_scrape=urls, allow_login=args.login, headless=headless_opt)
    else:
        interactive_menu()
