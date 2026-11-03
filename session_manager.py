"""
Session Manager: Handles Cloudflare Handshake and Session Cookie Bridging
Configured via settings.py and .env
"""

import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from settings import BASE_URL, HEADLESS_MODE, USER_AGENT, PROXY_URL
from logger import logger

def create_stealth_driver(headless=None):
    """Initializes a Chrome WebDriver with anti-detection options."""
    use_headless = HEADLESS_MODE if headless is None else headless
    options = Options()
    
    if use_headless:
        options.add_argument("--headless=new")
    else:
        options.add_argument("--start-maximized")
        
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Custom or Default User Agent from settings
    options.add_argument(f"user-agent={USER_AGENT}")

    # Optional Proxy
    if PROXY_URL:
        options.add_argument(f"--proxy-server={PROXY_URL}")
        logger.info(f"Using Proxy: {PROXY_URL}")
    
    driver = webdriver.Chrome(options=options)
    
    # Remove navigator.webdriver flag via CDP
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })
    except Exception as e:
        logger.debug(f"CDP script evaluation note: {e}")
        
    return driver

def init_scraper_session(allow_login=False, headless=None):
    """
    Launches Chrome to establish Cloudflare clearance, optionally allows 
    user to enter OTP to unmask phone numbers, then creates a fast Requests Session.
    """
    use_headless = HEADLESS_MODE if headless is None else headless
    logger.info(f"Initializing Chrome Session (Headless: {use_headless})...")
    
    driver = create_stealth_driver(headless=use_headless)
    
    try:
        driver.get(BASE_URL)
        time.sleep(3)
        
        if allow_login and not use_headless:
            print("\n" + "="*70)
            print("🔑 [OPTIONAL OTP LOGIN]")
            print("Agar aapko sabhi masked phone numbers (**********) unmask karne hain,")
            print("toh Chrome window me apna Mobile Number aur OTP enter karke Login kar lein.")
            print("Jab login complete ho jaye (ya skip karna ho), yahan console me ENTER press karein.")
            print("="*70)
            try:
                input("👉 Press ENTER to continue scraping... ")
            except EOFError:
                pass
        else:
            time.sleep(2)
            
        detected_ua = driver.execute_script("return navigator.userAgent;")
        cookies = driver.get_cookies()
        
    finally:
        driver.quit()
        logger.info("Chrome handshake complete. Cookies extracted successfully.")

    # Create Requests Session
    session = requests.Session()
    session.headers.update({
        "User-Agent": detected_ua or USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE_URL,
        "Connection": "keep-alive"
    })

    if PROXY_URL:
        session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
    return session
