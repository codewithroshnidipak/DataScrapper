"""
Scraper for Doctors and Dentists across all 16 Kolkata Locations
Extracts Business Name, Category, Area/Location, Phone Number, Full Address, Rating, Reviews, Website, Maps URL
"""

import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import re
import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from settings import OUTPUT_DIR, USER_AGENT
from logger import logger

LOCATIONS = [
    "Barrackpore",
    "Sodepur",
    "Khardah",
    "Belgharia",
    "Baguihati",
    "Dumdum",
    "Birati",
    "Saltlake",
    "New Town",
    "Kaikhali",
    "Dunlop",
    "Agarpara",
    "Parkstreet",
    "Park Circus",
    "Shakespeare Sarani",
    "Esplanade"
]

CATEGORIES = [
    "Dental Clinic",
    "Doctor Clinic"
]

PHONE_PATTERN = re.compile(
    r'(?:(?:\+91|0)[\s-]?)?(?:[6-9]\d{4}[\s-]?\d{5}|[6-9]\d{9}|033[\s-]?\d{3,4}[\s-]?\d{4}|18[06]0[\s-]?\d{3}[\s-]?\d{4})'
)

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--lang=en-US")
    return webdriver.Chrome(options=options)

def extract_leads_for_query(driver, category, location, max_results=6):
    query = f"{category} in {location} Kolkata"
    encoded_query = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded_query}"

    try:
        driver.get(url)
        time.sleep(3.5)
    except Exception as e:
        logger.error(f"Error fetching {query}: {e}")
        return []

    # Scroll results panel to load more listings
    try:
        panel = driver.find_element(By.XPATH, '//div[@role="feed"]')
        for _ in range(2):
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", panel)
            time.sleep(1.2)
    except Exception:
        pass

    cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
    results = []

    for card in cards[:max_results]:
        try:
            # 1. Name
            try:
                name_el = card.find_element(By.CSS_SELECTOR, "div.qBF1Pd")
                name = name_el.text.strip()
            except Exception:
                continue

            if not name:
                continue

            card_text = card.text

            # 2. Rating & Reviews
            rating = ""
            reviews = ""
            try:
                rating = card.find_element(By.CSS_SELECTOR, "span.MW4etd").text.strip()
            except Exception:
                pass
            try:
                rev_str = card.find_element(By.CSS_SELECTOR, "span.UY7F9").text.strip()
                reviews = re.sub(r'[^\d]', '', rev_str)
            except Exception:
                pass

            # 3. Direct Phone Number extraction
            phone = ""
            phone_match = PHONE_PATTERN.search(card_text)
            if phone_match:
                phone = phone_match.group(0).strip()

            # 4. Links (Website & Google Maps)
            website = ""
            maps_link = ""
            for a in card.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                aria = (a.get_attribute("aria-label") or "").lower()
                if "google.com/maps/place" in href and not maps_link:
                    maps_link = href
                elif "website" in aria or ("http" in href and "google.com" not in href and not website):
                    website = href

            # 5. Address & Specific Category from metadata line
            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
            meta_line = ""
            for l in lines:
                if "·" in l:
                    meta_line = l
                    break

            cat_label = category
            addr_snippet = f"{location}, Kolkata"
            if meta_line:
                parts = [p.strip() for p in meta_line.split("·")]
                if len(parts) >= 1 and parts[0]:
                    cat_label = parts[0]
                if len(parts) >= 2:
                    clean_parts = [
                        p for p in parts[1:]
                        if not re.search(r'\b(?:open|closed|pm|am)\b', p.lower())
                        and not re.search(r'\b\d{5,}\b', p)
                    ]
                    if clean_parts:
                        addr_snippet = ", ".join(clean_parts)

            full_address = f"{addr_snippet}, {location}, Kolkata".strip(', ')

            lead = {
                "Doctor / Clinic Name": name,
                "Specialization / Category": cat_label,
                "Area / Location": location,
                "City": "Kolkata",
                "Contact Number": phone or "Visit Clinic / Link",
                "Full Address": full_address,
                "Rating": rating,
                "Total Reviews": reviews,
                "Website": website,
                "Google Maps Link": maps_link
            }
            results.append(lead)

        except Exception as e:
            logger.debug(f"Error on card: {e}")

    return results

def main():
    print("""
================================================================================
 🏥 KOLKATA DOCTORS & DENTISTS B2B LEAD EXTRACTION 🏥
 Locations: 16 (Barrackpore, Sodepur, Salt Lake, Park Street, New Town, etc.)
 Categories: Dentists & Dental Clinics | Doctors & General Practitioners
================================================================================
""")
    driver = create_driver()
    all_leads = []
    total_steps = len(LOCATIONS) * len(CATEGORIES)
    step = 0

    try:
        for loc in LOCATIONS:
            for cat in CATEGORIES:
                step += 1
                print(f"[{step}/{total_steps}] Scraping: {cat} in {loc}...")
                leads = extract_leads_for_query(driver, category=cat, location=loc, max_results=5)
                print(f"      -> Found {len(leads)} leads in {loc}")
                all_leads.extend(leads)
                time.sleep(random.uniform(1.2, 2.0))
    finally:
        driver.quit()

    if not all_leads:
        print("❌ No leads extracted!")
        return

    df = pd.DataFrame(all_leads)
    initial_count = len(df)
    df.drop_duplicates(subset=["Doctor / Clinic Name", "Area / Location"], inplace=True)
    print(f"\nTotal collected: {initial_count} | Unique leads: {len(df)}")

    # File paths
    excel_path = OUTPUT_DIR / "KOLKATA_DOCTORS_AND_DENTISTS.xlsx"
    csv_path = OUTPUT_DIR / "KOLKATA_DOCTORS_AND_DENTISTS.csv"

    # Export CSV
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"📄 CSV Exported: {csv_path}")

    # Export Styled Excel
    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Doctors_Dentists_Kolkata", index=False)
            ws = writer.sheets["Doctors_Dentists_Kolkata"]

            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            h_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            h_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            border_side = Side(border_style="thin", color="D9D9D9")
            cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
            alt_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

            for col_idx in range(1, len(df.columns) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = h_fill
                cell.font = h_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for col_idx, col_name in enumerate(df.columns, 1):
                max_len = len(col_name)
                for row_idx in range(2, len(df) + 2):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    cell.border = cell_border
                    val_str = str(cell.value or "")
                    max_len = max(max_len, min(len(val_str), 45))
                    if row_idx % 2 == 0:
                        cell.fill = alt_fill

                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

            ws.row_dimensions[1].height = 28

        print(f"📊 Styled Excel Exported: {excel_path}")
    except Exception as e:
        df.to_excel(excel_path, index=False)
        print(f"📊 Excel Exported (standard): {excel_path}")

    print("\n🎉 DONE! All Doctor & Dentist leads successfully extracted across all 16 locations!")

if __name__ == "__main__":
    main()
