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

# --------------------------
# Logging
# --------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("PERSONAL_BOT")

# --------------------------
# Config & Files
# --------------------------
CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json") 
MESSAGES_FILE = os.environ.get("MESSAGES_FILE", "file.txt")
TARGETS_FILE = os.environ.get("TARGETS_FILE", "targets.txt") # Target User IDs/Thread IDs
DELAY = float(os.environ.get("DELAY", "40")) 
PORT = int(os.environ.get("PORT", "10000")) 

# --------------------------
# Load Config, Token, and Messages/Targets
# --------------------------

def load_config() -> Dict:
    """config.json फ़ाइल लोड करता है, जिसमें User Access Token शामिल है।"""
    if not os.path.exists(CONFIG_FILE):
        raise SystemExit(f"FATAL: Missing {CONFIG_FILE}. Create it with your token.")
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data.get("user_access_token"):
                 logger.error("Configuration file must contain 'user_access_token'.")
                 raise SystemExit("Missing User Access Token in config.json.")
            
            logger.info("Configuration loaded successfully.")
            return data
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
# **** TOKEN TO SESSION CONVERSION ****
# --------------------------

def build_session_from_token(token: str) -> requests.Session:
    """
    User Access Token का उपयोग करके एक requests.Session बनाता है।
    यह अनौपचारिक रूप से Facebook के OAuth रीडायरेक्ट का शोषण करके कुकीज़ प्राप्त करता है।
    """
    logger.info("Attempting UN-OFFICIAL User Access Token to Session conversion...")
    
    # यह URL और ID एक पुराने ज्ञात फेसबुक ऐप को इंगित करता है जो सत्र कुकीज़ सेट करता था।
    # यह कभी भी काम करना बंद कर सकता है।
    URL = "https://www.facebook.com/dialog/oauth"
    
    params = {
        'client_id': '124024574287414',  # एक ज्ञात क्लाइंट ID
        'redirect_uri': 'https://www.facebook.com/connect/login_success.html',
        'scope': 'public_profile', 
        'response_type': 'token',
        'access_token': token  # यहाँ User Access Token का उपयोग किया जाता है
    }

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    })

    try:
        # allow_redirects=False महत्वपूर्ण है क्योंकि यह हमें कुकीज़ मिलने के बाद रोकता है।
        response = s.get(URL, params=params, allow_redirects=False, timeout=20)
        
        if not response.cookies.keys():
             logger.error("Token-to-cookie failed. No session cookies received.")
             return None
        
        logger.info(f"Session created successfully with {len(response.cookies.keys())} cookies from Token.")
        return s

    except Exception as e:
        logger.error(f"Error during token-to-session creation: {e}")
        return None

# --------------------------
# Fetch form tokens (fb_dtsg, jazoest, etc.) - Same as your original script
# --------------------------
def fetch_form_tokens(session: requests.Session, target_id: str) -> Dict[str, str]:
    """mbasic conversation page से सभी आवश्यक छिपे हुए फ़ील्ड्स को एक्सट्रेक्ट करता है।"""
    # ... (आपके मूल कोड के समान)
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

# --------------------------
# send_message - Same as your original script
# --------------------------
def send_message(session: requests.Session, target_id: str, message: str) -> bool:
    """Cookie-backed session का उपयोग करके मैसेज भेजने का प्रयास करता है।"""
    tokens = fetch_form_tokens(session, target_id)
    if not tokens:
        logger.warning("Tokens missing for target %s — cannot send.", target_id)
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
            logger.info("Message posted to %s (Status: 302 Redirect)", target_id)
            return True
        else:
            if "Something Went Wrong" in r.text or "Error" in r.text or "Security Check" in r.text:
                logger.warning("Send failed. Security check/error page received for %s", target_id)
                return False
            logger.warning("Send failed status=%s for %s. Unexpected response.", r.status_code, target_id)
            return False
    except Exception as e:
        logger.exception("Exception sending to %s: %s", target_id, e)
        return False

# --------------------------
# Worker loop (Modified to use Token-Generated Session)
# --------------------------
def worker_loop():
    try:
        cfg = load_config()
    except SystemExit:
        return
    
    # TOKEN का उपयोग करके SESSION बनाएँ
    session = build_session_from_token(cfg["user_access_token"])
    if not session:
        logger.error("Session creation failed (Token/Method problem). Worker exit.")
        return

    messages = read_lines_strip(MESSAGES_FILE)
    targets = read_lines_strip(TARGETS_FILE)

    if not messages or not targets:
        logger.error("Messages or Targets file missing/empty.")
        return

    logger.info("Worker started: %d messages x %d targets. Delay: %s sec", len(messages), len(targets), DELAY)

    try:
        while True:
            logger.info("Starting new cycle of messages...")
            for t in targets:
                for m in messages:
                    logger.info("Sending message to %s: %s", t, (m[:120] + '...') if len(m)>120 else m)
                    # यहाँ टोकन-जनरेटेड सेशन का उपयोग किया जाता है
                    ok = send_message(session, t, m) 
                    
                    if ok:
                        logger.info("Message sent successfully.")
                    else:
                        logger.warning("Failed to send. Check if account is blocked/token expired.")
                    
                    time.sleep(DELAY) 
            
            logger.info("Cycle complete. Restarting loop after 60 seconds...")
            time.sleep(60) 

    except Exception as e:
        logger.exception("Worker loop crashed: %s", e)

# --------------------------
# Flask app (Render expects a web process)
# --------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot running. Mode: TOKEN -> M-Basic Web Scraping (Unofficial)"

if __name__ == "__main__":
    # start worker thread
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    # run flask
    app.run(host="0.0.0.0", port=PORT)
