import requests
import json
import os
import time

# Configuration
H1_GRAPHQL_URL = "https://hackerone.com/graphql"
# The Discord Webhook URL should be placed here or set via environment variable
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_HERE")
STATE_FILE = "last_disclosed_id.txt"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

QUERY = """
query {
  reports(
    first: 5,
    where: { disclosed_at: { _is_null: false } }
  ) {
    nodes {
      _id
      title
      url
      severity {
        rating
      }
      team {
        handle
      }
    }
  }
}
"""

def fetch_hacktivity():
    """
    Sends a GraphQL query to HackerOne to retrieve the most recently
    disclosed vulnerability reports using the reports field.
    """
    payload = {"query": QUERY}
    try:
        response = requests.post(H1_GRAPHQL_URL, json=payload, headers=HEADERS, timeout=10)
        print(f"[*] Response Status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        if 'errors' in data:
            print(f"[!] GraphQL Errors: {json.dumps(data['errors'], indent=2)}")
            return None
            
        nodes = data.get("data", {}).get("reports", {}).get("nodes", [])
        return nodes
    except Exception as e:
        print(f"[!] Error fetching Hacktivity: {e}")
        return None

def send_to_discord(report):
    """
    Formats report data and sends it as an embed to the configured
    Discord webhook.
    """
    if DISCORD_WEBHOOK_URL == "YOUR_WEBHOOK_HERE":
        print("[!] Discord Webhook URL not set. Skipping ping.")
        return

    if not report:
        return

    report_id = report.get("_id")
    title = report.get("title")
    # API URL might already be absolute
    raw_url = report.get("url")
    url = raw_url if raw_url.startswith("http") else f"https://hackerone.com{raw_url}"
    
    team = report.get("team", {}).get("handle")
    
    severity_obj = report.get("severity")
    severity = "N/A"
    if severity_obj and severity_obj.get("rating"):
        severity = severity_obj.get("rating").capitalize()

    embed = {
        "title": f"New Disclosure: {title}",
        "url": url,
        "color": 3447003,
        "fields": [
            {"name": "Program", "value": team, "inline": True},
            {"name": "Severity", "value": severity, "inline": True},
            {"name": "Report ID", "value": f"#{report_id}", "inline": True}
        ],
        "footer": {"text": "HackerOne Monitor"}
    }

    payload = {"embeds": [embed]}
    try:
        print(f"[*] Sending payload to Discord: {json.dumps(payload, indent=2)}")
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        print(f"[+] Successfully sent report #{report_id} to Discord.")
    except Exception as e:
        print(f"[!] Error sending to Discord: {e}")
        if 'res' in locals() and res.text:
            print(f"[*] Discord Response: {res.text}")

def get_last_id():
    """
    Reads the last processed report ID from a local text file to 
    prevent duplicate notifications.
    
    Returns:
        str: The last seen report ID, or None if the file doesn't exist.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_id(report_id):
    """
    Saves the ID of the most recently processed report to a local 
    text file.
    
    Args:
        report_id (str): The ID to save.
    """
    with open(STATE_FILE, "w") as f:
        f.write(str(report_id))

import argparse

# ... existing code ...

def run_monitor(run_once=False):
    """
    The main execution loop. It fetches the latest reports, compares 
    the newest one to the last seen ID, and triggers a Discord ping 
    for any new items found.
    """
    print("[*] Starting HackerOne Hacktivity Monitor...")
    while True:
        nodes = fetch_hacktivity()
        if nodes:
            # The first node is the latest report
            latest_report = nodes[0]
            
            if latest_report:
                latest_id = str(latest_report.get("_id"))
                last_seen_id = get_last_id()

                if latest_id != last_seen_id:
                    print(f"[*] New report detected: {latest_id}")
                    send_to_discord(latest_report)
                    save_last_id(latest_id)
                else:
                    print(f"[*] No new disclosures. (Last ID: {last_seen_id})")
            else:
                print("[!] No reports found in results.")

        if run_once:
            break

        # Sleep for 10 minutes before checking again
        time.sleep(600)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HackerOne Hacktivity Monitor")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron usage)")
    args = parser.parse_args()
    
    run_monitor(run_once=args.once)
