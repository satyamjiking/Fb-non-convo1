import requests
import json
import time
import sys

# --- 1. सभी आवश्यक डेटा फ़ाइल से पढ़ें ---
try:
    with open("my_token.txt", "r") as f:
        ACCESS_TOKEN = f.read().strip()
        if not ACCESS_TOKEN:
            raise ValueError("my_token.txt is empty.")
    
    with open("targets.txt", "r") as f:
        TARGETS = [line.strip() for line in f if line.strip()] # हर लाइन से ID पढ़ें
        if not TARGETS:
            raise ValueError("targets.txt is empty.")
        
    with open("file.txt", "r") as f:
        MESSAGES = [line.strip() for line in f if line.strip()] # हर लाइन को एक अलग मैसेज मानें
        if not MESSAGES:
            raise ValueError("file.txt is empty.")
            
except FileNotFoundError as e:
    print(f"\n[CRITICAL ERROR] File not found: {e.filename}. Please create this file.")
    sys.exit(1)
except ValueError as e:
    print(f"\n[CRITICAL ERROR] {e}")
    sys.exit(1)

# --- 2. मुख्य लूप (Target और Message के लिए) ---
delay_time = 120 # 120 सेकंड का विलंब

print("\n=============================================")
print(f"Starting Scan: {len(TARGETS)} targets and {len(MESSAGES)} messages.")
print(f"Delay set to: {delay_time} seconds per message.")
print("=============================================")

success_count = 0

for target_id in TARGETS:
    for message_content in MESSAGES:
        # API एंडपॉइंट सेट करें
        URL = f"https://graph.facebook.com/v15.0/{target_id}/feed"
        
        data = {
            'message': message_content,
            'access_token': ACCESS_TOKEN
        }
        
        print(f"\n[INFO] Sending message to Target ID: {target_id}")
        print(f"[INFO] Message: '{message_content[:30]}...'")

        try:
            response = requests.post(URL, data=data)
            response_data = response.json()

            if response.status_code == 200:
                print(f"✅ SUCCESS! Post ID: {response_data.get('id')}")
                success_count += 1
            else:
                print(f"❌ FAILED! Status: {response.status_code}")
                print(f"Error: {response_data.get('error', {}).get('message')}")
                # अगर टोकन फेल हुआ, तो पूरा लूप रोक दें
                if "Error validating access token" in str(response_data):
                    print("[FATAL] Access Token Invalid. Stopping script.")
                    sys.exit(1)

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Network error: {e}")

        # विलंब (Delay)
        if (target_id != TARGETS[-1] or message_content != MESSAGES[-1]):
            print(f"--- Pausing for {delay_time} seconds ---")
            time.sleep(delay_time)

print("\n=============================================")
print(f"✅ Final Result: {success_count} messages sent successfully.")
print("✅ PROJECT COMPLETE: This output is your final proof.")
print("=============================================")
