import os
import json
import time
import logging
import threading
import re
from typing import List, Dict
from flask import Flask
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

# --------------------------
# Logging Setup
# --------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("FINAL_BOT")

# --------------------------
# Config & Files
# --------------------------
CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json") 
MESSAGES_FILE = os.environ.get("MESSAGES_FILE", "file.txt")
TARGETS_FILE = os.environ.get("TARGETS_FILE", "targets.txt") # Target User/Group IDs
PORT = int(os.environ.get("PORT", "10000")) 

# --------------------------
# Loaders
# --------------------------

def load_config() -> Dict:
    """config.json फ़ाइल से सभी डेटा लोड करता है।"""
    if not os.path.exists(CONFIG_FILE):
        raise SystemExit(f"FATAL: Missing {CONFIG_FILE}. Create it first.")
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Token की उपस्थिति प्रोजेक्ट की आवश्यकता के लिए जाँचें
            if not data.get("user_access_token"):
                 logger.warning("WARNING: 'user_access_token' is missing. Add it for project requirement.")
            
            # कुकीज़ की उपस्थिति क्रियान्वयन (Execution) के लिए जाँचें
            if not data.get("manual_cookies"):
                 logger.error("FATAL: 'manual_cookies' are required for login.")
                 raise SystemExit("Missing 'manual_cookies' in config.json.")
                 
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"FATAL JSON DECODE ERROR: config.json is invalid JSON. Details: {e}")
        raise SystemExit("Fix the JSON format in config.json.")
    except Exception as e:
        logger.exception("Config load error: %s", e)
        raise SystemExit("Error loading configuration.")

def read_lines_strip(path: str) -> List[str]:
    """टेक्स्ट फ़ाइल से मैसेज/टारगेट पढ़ता है।"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]

# --------------------------
# Session Builder (Authentication)
# --------------------------

def build_session(config: Dict) -> requests.Session:
    """मैन्युअल कुकीज़ का उपयोग करके सक्रिय सत्र (Active Session) बनाता है।"""
    manual_cookies = config.get("manual_cookies", [])

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    })

    if not manual_cookies:
        logger.error("No cookies provided for session creation.")
        return None

    # कुकीज़ को सेशन में सेट करें
    for c in manual_cookies:
        # सुनिश्चित करें कि कुकी में 'domain' मौजूद है
        domain = c.get("domain") if c.get("domain") else ".facebook.com"
        s.cookies.set(c.get("name"), c.get("value"), domain=domain)
    
    logger.info(f"Attempting login check using {len(manual_cookies)} cookies...")
    
    # लॉगिन की जाँच करें: mbasic पेज पर जाकर देखें कि यह हमें लॉगिन पेज पर रीडायरेक्ट करता है या नहीं
    try:
        r = s.get("https://mbasic.facebook.com/", timeout=15)
        
        # यदि URL में login.php नहीं है, तो लॉगिन सफल है
        if "login.php" not in r.url:
            logger.info("SUCCESS: Session created using active cookies. Logged in as personal ID.")
            return s
        else:
            logger.error("Login failed. Cookies are likely expired or invalid.")
            return None
    except Exception as e:
        logger.error(f"Session check failed: {e}")
        return None

# --------------------------
# Message Sender (Core Logic)
# --------------------------

def fetch_form_tokens(session: requests.Session, target_id: str) -> Dict[str, str]:
    """mbasic conversation page से fb_dtsg और अन्य छिपे हुए फ़ील्ड्स को एक्सट्रेक्ट करता है।"""
    url = f"https://mbasic.facebook.com/messages/thread/{target_id}"
    tokens = {}
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            logger.warning("Could not fetch thread page %s status=%s", url, r.status_code)
            return {}
        
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.find_all("input", {"type": "hidden"}):
            name = el.get("name")
            value = el.get("value")
            if name and value:
                tokens[name] = value

        if "fb_dtsg" not in tokens:
            m = re.search(r'name="fb_dtsg"\s+value="([^"]+)"', r.text)
            if m:
                tokens["fb_dtsg"] = m.group(1)
            
        if 'body' in tokens:
            del tokens['body'] 
            
        return tokens
    except Exception as e:
        logger.exception("Token fetch failed for %s: %s", target_id, e)
        return {}

def send_message(session: requests.Session, target_id: str, message: str) -> bool:
    """सक्रिय सत्र का उपयोग करके मैसेज भेजता है।"""
    tokens = fetch_form_tokens(session, target_id)
    if not tokens:
        logger.warning("Tokens missing for target %s — cannot send. Session might be invalid.", target_id)
        return False

    send_url = f"https://mbasic.facebook.com/messages/send/?ids[{target_id}]=1"

    payload = {
        "body": message,
        **tokens 
    }
    
    if 'send' not in payload and 'Send' not in payload:
        payload['send'] = 'Send' 

    headers = {
        "Referer": f"https://mbasic.facebook.com/messages/thread/{target_id}",
        "Origin": "https://mbasic.facebook.com",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        r = session.post(send_url, data=payload, headers=headers, allow_redirects=False, timeout=20)
        
        if r.status_code == 302:
            return True
        else:
            if "Something Went Wrong" in r.text or "Error" in r.text or "Security Check" in r.text:
                logger.warning("Send failed. Security check/error page received.")
                return False
            logger.warning("Send failed status=%s. Unexpected response.", r.status_code)
            return False
    except Exception as e:
        logger.exception("Exception sending to %s: %s", target_id, e)
        return False

# --------------------------
# Worker Loop
# --------------------------
def worker_loop():
    try:
        cfg = load_config()
    except SystemExit:
        return
    
    session = build_session(cfg)
    if not session:
        logger.error("Final session could not be established. Worker exit.")
        return

    messages = read_lines_strip(MESSAGES_FILE)
    targets = read_lines_strip(TARGETS_FILE)

    DELAY = float(cfg.get("delay_between_messages", 40))
    CYCLE_DELAY = float(cfg.get("cycle_delay", 60))
    
    if not messages or not targets:
        logger.error("Messages or Targets file missing/empty. Worker exit.")
        return

    logger.info("Worker started: %d messages x %d targets. Delay: %s sec", len(messages), len(targets), DELAY)

    try:
        while True:
            logger.info("Starting new cycle of messages...")
            for t in targets:
                for m in messages:
                    logger.info("Sending to %s: %s", t, (m[:100] + '...') if len(m)>100 else m)
                    ok = send_message(session, t, m) 
                    
                    if ok:
                        logger.info("Message sent successfully (Status: 302).")
                    else:
                        logger.warning("Failed to send. Check logs for security errors.")
                    
                    time.sleep(DELAY) 
            
            logger.info("Cycle complete. Restarting loop after %s seconds...", CYCLE_DELAY)
            time.sleep(CYCLE_DELAY) 

    except Exception as e:
        logger.critical("Worker loop crashed: %s", e)

# --------------------------
# Flask App (for Render deployment)
# --------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot running. Mode: Active Cookie-Based (M-Basic). Check logs."

if __name__ == "__main__":
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=PORT)
