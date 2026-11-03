"""
Multi-Location Local Leads Scraper (Google Maps Engine)
Extracts hyper-local leads across multiple areas/neighborhoods (e.g. Kolkata locations)
"""

import os
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import re
import time
import random
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from settings import (
    BASE_DIR,
    OUTPUT_DIR,
    HEADLESS_MODE,
    USER_AGENT
)
from logger import logger

LOCAL_EXCEL_OUTPUT = OUTPUT_DIR / "LOCAL_LEADS_KOLKATA.xlsx"
LOCAL_CSV_OUTPUT = OUTPUT_DIR / "LOCAL_LEADS_KOLKATA.csv"

def get_maps_driver(headless=True):
    """Initializes Chrome driver optimized for Google Maps scraping."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    else:
        options.add_argument("--start-maximized")
        
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--lang=en-US")
    
    driver = webdriver.Chrome(options=options)
    return driver

def scrape_area_leads(driver, category, location, city="Kolkata", max_results=10):
    """Scrapes local business leads for a specific category and location."""
    query = f"{category} in {location} {city}".strip()
    encoded_query = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded_query}"
    
    logger.info(f"📍 Scraping Location: '{location}' for '{category}'...")
    try:
        driver.get(url)
        time.sleep(3.5)
    except Exception as e:
        logger.error(f"Failed to load search page for {query}: {e}")
        return []

    # Scroll down the results panel to load more cards
    try:
        panel = driver.find_element(By.XPATH, '//div[@role="feed"]')
        for _ in range(2):
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", panel)
            time.sleep(1.2)
    except Exception:
        pass

    cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
    logger.info(f"   Found {len(cards)} places in {location}")

    leads = []
    for card in cards[:max_results]:
        try:
            # 1. Business Name
            name = ""
            try:
                name_el = card.find_element(By.CSS_SELECTOR, "div.qBF1Pd")
                name = name_el.text.strip()
            except Exception:
                continue

            if not name:
                continue

            # 2. Rating & Review Count
            rating = ""
            reviews = ""
            try:
                rating = card.find_element(By.CSS_SELECTOR, "span.MW4etd").text.strip()
            except Exception:
                pass
            try:
                rev_text = card.find_element(By.CSS_SELECTOR, "span.UY7F9").text.strip()
                reviews = re.sub(r'[^\d]', '', rev_text)
            except Exception:
                pass

            # 3. Phone Number (direct regex extraction from card text)
            card_text = card.text
            phone = ""
            phone_pattern = re.search(r'(\+91[\s-]?)?[0]?[6-9]\d{4}[\s-]?\d{5}|033[\s-]?\d{6,8}', card_text)
            if phone_pattern:
                phone = phone_pattern.group(0).strip()

            # 4. Website & Google Maps Link
            website = ""
            maps_link = ""
            for a in card.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                aria = (a.get_attribute("aria-label") or "").lower()
                if "google.com/maps/place" in href and not maps_link:
                    maps_link = href
                elif "website" in aria or ("http" in href and "google.com" not in href and not website):
                    website = href

            # 5. Address / Category breakdown from lines
            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
            meta_line = ""
            for l in lines:
                if "·" in l:
                    meta_line = l
                    break

            cat_name = category
            address_snippet = f"{location}, {city}"
            if meta_line:
                parts = [p.strip() for p in meta_line.split("·")]
                if len(parts) >= 1 and parts[0]:
                    cat_name = parts[0]
                if len(parts) >= 2:
                    address_snippet = ", ".join([p for p in parts[1:] if not re.search(r'[0-9]{4,}', p) and "open" not in p.lower() and "closed" not in p.lower()]) or address_snippet

            lead_entry = {
                "Business Name": name,
                "Category / Industry": cat_name,
                "Area / Location": location,
                "City": city,
                "Phone Number": phone or "Available via Profile",
                "Full Address": f"{address_snippet}, {location}, {city}".strip(', '),
                "Website": website,
                "Rating": rating,
                "Review Count": reviews,
                "Source Link": maps_link
            }
            leads.append(lead_entry)

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")

    logger.info(f"   ✅ Collected {len(leads)} leads from {location}")
    return leads

def run_multi_location_scraper(category="Real Estate Agents", locations_file="locations.txt", max_per_location=5):
    """Runs scraping across all locations defined in locations.txt."""
    loc_path = BASE_DIR / locations_file
    if not loc_path.exists():
        logger.error(f"Locations file '{locations_file}' not found!")
        return

    with open(loc_path, "r", encoding="utf-8") as f:
        locations = [line.strip().strip(',') for line in f if line.strip() and not line.startswith('#')]

    print(f"\n🚀 Running Multi-Location Scraper for: '{category}' across {len(locations)} Kolkata areas...")
    driver = get_maps_driver(headless=True)
    all_leads = []

    try:
        for idx, loc in enumerate(locations, 1):
            print(f"[{idx}/{len(locations)}] Processing: {loc}...")
            leads = scrape_area_leads(driver, category=category, location=loc, city="Kolkata", max_results=max_per_location)
            all_leads.extend(leads)
            time.sleep(random.uniform(1.0, 2.0))
    finally:
        driver.quit()

    if not all_leads:
        print("⚠️ Koi leads extract nahi ho paye.")
        return

    df = pd.DataFrame(all_leads)
    df.drop_duplicates(subset=["Business Name", "Area / Location"], inplace=True)

    # Export CSV
    df.to_csv(LOCAL_CSV_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n📄 CSV Saved: {LOCAL_CSV_OUTPUT}")

    # Export Excel with Styling
    try:
        with pd.ExcelWriter(LOCAL_EXCEL_OUTPUT, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Kolkata_Leads", index=False)
            ws = writer.sheets["Kolkata_Leads"]
            
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
                    
        print(f"📊 Styled Excel Saved: {LOCAL_EXCEL_OUTPUT}")
    except Exception as e:
        df.to_excel(LOCAL_EXCEL_OUTPUT, index=False)
        print(f"📊 Excel Saved (standard): {LOCAL_EXCEL_OUTPUT}")

    print(f"\n🎉 DONE! Total {len(df)} leads extracted across Kolkata locations!")
    print("\nSample Preview:")
    print(df[["Business Name", "Category / Industry", "Area / Location", "Phone Number"]].head(8).to_string(index=False))

if __name__ == "__main__":
    cat = sys.argv[1] if len(sys.argv) > 1 else "Real Estate Agents"
    run_multi_location_scraper(category=cat, locations_file="locations.txt", max_per_location=3)
