"""
Core Scraping Engine for Maharashtra Directory
Configured via settings.py and .env
"""

import re
import json
import time
import random
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from settings import (
    BASE_URL,
    SEARCH_URL,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    PAGE_TIMEOUT,
    MAX_RETRIES
)
from logger import logger

class CompanyDetailParser:
    """Parses full company details from a company info page HTML."""
    
    @staticmethod
    def parse(html_content, url=""):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. JSON-LD Schema (High fidelity structured data)
        schema_data = {}
        for s in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(s.string)
                if isinstance(data, dict) and any(t in str(data.get('@type')) for t in ['LocalBusiness', 'Organization']):
                    schema_data = data
                    break
            except Exception:
                pass

        # 2. Company Name
        h1 = soup.find('h1', class_='cc-company-name') or soup.find('h1')
        name = h1.get_text(strip=True) if h1 else schema_data.get('name', '')
        
        # 3. Contact Person / Lead
        contact_person = ""
        user_row = soup.find('i', class_=lambda c: c and 'fa-user' in c)
        if user_row and user_row.parent:
            contact_person = user_row.parent.get_text(' ', strip=True)
            contact_person = re.sub(r'^(Contact\s*Person\s*:?|Contact\s*:?)', '', contact_person, flags=re.I).strip()
        if not contact_person and schema_data.get('employee'):
            contact_person = schema_data['employee'].get('name', '')

        # 4. Address Details
        address = ""
        addr_el = soup.find(class_='cc-address-text')
        if addr_el:
            address = addr_el.get_text(' ', strip=True)
        else:
            marker = soup.find('i', class_=lambda c: c and 'fa-map-marker' in c)
            if marker and marker.parent:
                address = marker.parent.get_text(' ', strip=True)

        locality = ""
        region = ""
        pincode = ""
        if schema_addr := schema_data.get('address'):
            locality = schema_addr.get('addressLocality', '')
            region = schema_addr.get('addressRegion', '')
            pincode = str(schema_addr.get('postalCode', ''))
            if not address:
                street = schema_addr.get('streetAddress', '')
                address = f"{street}, {locality}, {region} - {pincode}".strip(', -')

        # Clean address character artifacts
        address = address.replace('', '-').replace('\u2014', '-').strip()

        # 5. Phone / Mobile / Landline Info
        phone_list = []
        sidebar = soup.find('div', class_='cc-sidebar-section') or soup
        for p_icon in sidebar.find_all('i', class_=lambda c: c and ('fa-phone' in c or 'fa-mobile' in c)):
            row = p_icon.parent
            if row:
                txt = row.get_text(' ', strip=True)
                # Filter out navigation / modal text
                txt = re.sub(r'\(View\)', '', txt).strip()
                if txt and not any(bad in txt.lower() for bad in ['advertising', 'send otp', 'enquiry', 'callback']):
                    if txt not in phone_list:
                        phone_list.append(txt)

        phone_str = " | ".join(phone_list) if phone_list else "Not Public / OTP required"

        # 6. Website
        website = ""
        globe_icon = sidebar.find('i', class_=lambda c: c and 'fa-globe' in c)
        if globe_icon and globe_icon.parent:
            w_link = globe_icon.parent.find('a', href=True)
            if w_link and w_link['href'].startswith('http'):
                website = w_link['href']
            else:
                txt = globe_icon.parent.get_text(' ', strip=True)
                txt = re.sub(r'\(View\)', '', txt).strip()
                if not any(bad in txt.lower() for bad in ['design', 'hosting', 'advertising']):
                    website = txt

        # 7. Description / Products
        desc = ""
        desc_el = soup.find(class_='cc-company-sub')
        if desc_el:
            desc = desc_el.get_text(' ', strip=True)
        elif schema_data.get('description'):
            desc = schema_data['description']
        desc = desc.replace('', '-').replace('\u2014', '-').strip()

        return {
            "Company Name": name,
            "Contact Person / Lead": contact_person,
            "City / Locality": locality,
            "State": region,
            "Pincode": pincode,
            "Full Address": address,
            "Phone / Contact Info": phone_str,
            "Website": website,
            "Description": desc,
            "Profile Link": url
        }


class LeadScraper:
    """Orchestrates scraping of company lists and search results."""
    
    def __init__(self, session):
        self.session = session

    def scrape_single_url(self, url):
        """Scrapes details from a single company profile URL with retries."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=PAGE_TIMEOUT)
                if resp.status_code == 200:
                    return CompanyDetailParser.parse(resp.text, url)
                else:
                    logger.warning(f"[HTTP {resp.status_code}] (Attempt {attempt}/{MAX_RETRIES}) Failed: {url}")
            except Exception as e:
                logger.warning(f"Connection error (Attempt {attempt}/{MAX_RETRIES}) on {url}: {e}")
            time.sleep(1)
        return None

    def scrape_links_list(self, urls):
        """Scrapes a list of company links sequentially."""
        results = []
        total = len(urls)
        logger.info(f"Scraping {total} company URLs...")
        
        for idx, url in enumerate(urls, 1):
            logger.info(f"[{idx}/{total}] Scraping: {url}")
            data = self.scrape_single_url(url)
            if data and data.get("Company Name"):
                results.append(data)
                comp = data["Company Name"]
                lead = data.get("Contact Person / Lead") or "N/A"
                city = data.get("City / Locality") or "N/A"
                logger.info(f"   -> Found: {comp} | Lead: {lead} | City: {city}")
            else:
                logger.warning(f"   -> No data extracted for: {url}")
                
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
            
        return results

    def search_by_keyword(self, keyword, location=None, max_results=50, enrich_details=True):
        """
        Searches Maharashtra Directory for a product/keyword,
        optionally filters by location/city, and extracts all leads.
        """
        logger.info(f"Searching catalog for: '{keyword}'" + (f" in '{location}'" if location else ""))
        search_req_url = f"{SEARCH_URL}?term={quote(keyword)}"
        
        try:
            resp = self.session.get(search_req_url, timeout=PAGE_TIMEOUT)
            if resp.status_code != 200:
                logger.error(f"Search request failed with status {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Search connection error: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        rc_cards = soup.find_all('div', class_='rc')
        logger.info(f"Found {len(rc_cards)} listings on result page.")
        
        collected_items = []
        loc_filter = location.strip().lower() if location else None
        
        for rc in rc_cards:
            title_div = rc.find(class_='rc-title')
            if not title_div:
                continue
                
            comp_link_el = title_div.find('a', href=True)
            if not comp_link_el:
                continue
                
            comp_name = comp_link_el.get_text(strip=True)
            lead_attr = comp_link_el.get('title', '')
            lead_name = lead_attr.replace('Contact:', '').strip() if 'Contact:' in lead_attr else lead_attr
            
            href = comp_link_el['href']
            profile_url = href if href.startswith('http') else BASE_URL + href
            
            # Location snippet from card
            meta_div = rc.find(class_='rc-meta')
            card_loc = meta_div.get_text(' ', strip=True) if meta_div else ""
            
            # Filter by location if specified
            if loc_filter:
                card_text_lower = (card_loc + " " + profile_url + " " + comp_name).lower()
                if loc_filter not in card_text_lower:
                    continue
                    
            # Description from card
            all_metas = rc.find_all(class_='rc-meta')
            desc_text = all_metas[-1].get_text(' ', strip=True) if all_metas else ""
            desc_text = re.sub(r'\.\.\.More$', '', desc_text).strip()
            
            card_item = {
                "Company Name": comp_name,
                "Contact Person / Lead": lead_name,
                "City / Locality": card_loc.split('-')[0].strip() if '-' in card_loc else card_loc,
                "State": "MAHARASHTRA",
                "Pincode": re.search(r'\b\d{6}\b', card_loc).group(0) if re.search(r'\b\d{6}\b', card_loc) else "",
                "Full Address": card_loc,
                "Phone / Contact Info": "View via Profile",
                "Website": "",
                "Description": desc_text,
                "Profile Link": profile_url
            }
            collected_items.append(card_item)
            
            if len(collected_items) >= max_results:
                break

        logger.info(f"Filtered {len(collected_items)} companies matching location.")

        # Deep detail enrichment
        if enrich_details and collected_items:
            logger.info("Extracting deep profile details (Full Address, Phones, Websites)...")
            detailed_items = []
            for i, item in enumerate(collected_items, 1):
                p_url = item["Profile Link"]
                logger.info(f"[{i}/{len(collected_items)}] Deep scraping: {item['Company Name']}")
                deep_data = self.scrape_single_url(p_url)
                if deep_data and deep_data.get("Company Name"):
                    if not deep_data.get("Contact Person / Lead") and item.get("Contact Person / Lead"):
                        deep_data["Contact Person / Lead"] = item["Contact Person / Lead"]
                    detailed_items.append(deep_data)
                else:
                    detailed_items.append(item)
                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
            return detailed_items

        return collected_items
