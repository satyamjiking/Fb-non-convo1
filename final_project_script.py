import requests
import json
import time
import sys

# --- 1. सभी आवश्यक डेटा फ़ाइल से पढ़ें ---
try:
    with open("my_token.txt", "r") as f:
        ACCESS_TOKEN = f.read().strip()
    
    with open("targets.txt", "r") as f:
        TARGETS = [line.strip() for line in f if line.strip()]
        
    with open("file.txt", "r") as f:
        MESSAGES = [line.strip() for line in f if line.strip()] 
        
    if not TARGETS or not MESSAGES or not ACCESS_TOKEN:
         raise ValueError("One of the required files is empty.")
            
except FileNotFoundError as e:
    print(f"\n[CRITICAL ERROR] File not found: {e.filename}. Please check files.")
    sys.exit(1)
except ValueError as e:
    print(f"\n[CRITICAL ERROR] Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n[CRITICAL ERROR] An unknown error occurred while reading files: {e}")
    sys.exit(1)

# --- 2. मुख्य लूप और विलंब सेटिंग्स ---
# 120 सेकंड का विलंब (delay)
DELAY_TIME = 120 
success_count = 0

print("\n=============================================")
print(f"Starting Scan: {len(TARGETS)} targets, {len(MESSAGES)} messages.")
print(f"Delay set to: {DELAY_TIME} seconds per message.")
print("=============================================")

# Target Loop: हर टारगेट ID पर जाएँ
for target_id in TARGETS:
    print(f"\n---- TARGETING ID: {target_id} ----")
    
    # Message Loop: हर रोल नंबर को अलग मैसेज के रूप में भेजें
    for message_content in MESSAGES:
        # **अंतिम API एंडपॉइंट: सीधा पोस्ट /posts**
        URL = f"https://graph.facebook.com/v15.0/{target_id}/posts"
        
        # सरलतम डेटा संरचना
        data = {
            'message': message_content,
            'access_token': ACCESS_TOKEN
        }
        
        print(f"[INFO] Sending: '{message_content}'")

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
            print(f"--- Pausing for {DELAY_TIME} seconds ---")
            time.sleep(DELAY_TIME)

print("\n=============================================")
print(f"✅ Final Result: {success_count} messages sent successfully.")
print("✅ PROJECT COMPLETE: This output is your final proof.")
print("=============================================")
