import requests
import json
import os
import time
import signal
import sys

# Configuration
H1_GRAPHQL_URL = "https://hackerone.com/graphql"
# The Discord Webhook URL should be set via the `DISCORD_WEBHOOK_URL` environment variable
# or replaced here with a literal webhook URL. Using the webhook URL as the env var name
# was a bug; use a proper variable name instead.
# Default webhook (will be used if `DISCORD_WEBHOOK_URL` env var is not set).
DEFAULT_DISCORD_WEBHOOK = (
    "WEBHOOKHERE"
)
# Read from environment, but fall back to the provided webhook.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", DEFAULT_DISCORD_WEBHOOK)
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
        try:
            data = response.json()
        except ValueError:
            print("[!] Invalid JSON received from HackerOne")
            return None
        
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
    title = report.get("title") or "No title"
    # API URL might already be absolute; guard for missing values
    raw_url = report.get("url") or ""
    if raw_url.startswith("http"):
        url = raw_url
    elif raw_url:
        url = f"https://hackerone.com{raw_url}"
    else:
        url = "https://hackerone.com/"

    team = (report.get("team") or {}).get("handle") or "Unknown"

    severity_obj = report.get("severity") or {}
    severity = "N/A"
    rating = severity_obj.get("rating")
    if rating:
        severity = str(rating).capitalize()

    report_id_str = f"#{report_id}" if report_id is not None else "N/A"

    embed = {
        "title": f"New Disclosure: {title}",
        "url": url,
        "color": 3447003,
        "fields": [
            {"name": "Program", "value": team, "inline": True},
            {"name": "Severity", "value": severity, "inline": True},
            {"name": "Report ID", "value": report_id_str, "inline": True}
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

shutdown_requested = False

def _signal_handler(sig, frame):
    global shutdown_requested
    print(f"[*] Signal received ({sig}). Shutting down...")
    sys.stdout.flush()
    shutdown_requested = True


def run_monitor(run_once=False, interval=1800, force=False):
    """
    The main execution loop. It fetches the latest reports, compares 
    the newest one to the last seen ID, and triggers a Discord ping 
    for any new items found.
    """
    global shutdown_requested
    print("[*] Starting HackerOne Hacktivity Monitor...")
    while True:
        nodes = fetch_hacktivity()
        if nodes:
            # The first node is the latest report
            latest_report = nodes[0]
            
            if latest_report:
                latest_id = str(latest_report.get("_id"))
                last_seen_id = get_last_id()

                if force or latest_id != last_seen_id:
                    print(f"[*] New report detected: {latest_id}")
                    send_to_discord(latest_report)
                    save_last_id(latest_id)
                else:
                    print(f"[*] No new disclosures. (Last ID: {last_seen_id})")
            else:
                print("[!] No reports found in results.")

        if run_once or shutdown_requested:
            break

        # Sleep in short increments so we can exit quickly on SIGINT/SIGTERM.
        print(f"[*] Sleeping for {interval} seconds (interrupt to stop)...")
        sys.stdout.flush()
        slept = 0
        try:
            while slept < interval:
                if shutdown_requested:
                    break
                time.sleep(1)
                slept += 1
        except KeyboardInterrupt:
            # Allow Ctrl+C to request shutdown and exit the loop promptly
            shutdown_requested = True
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HackerOne Hacktivity Monitor")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron usage)")
    parser.add_argument("--webhook", help="Discord webhook URL to use for this run (overrides env)")
    parser.add_argument("--force", action="store_true", help="Send the latest report even if it matches the saved last ID")
    parser.add_argument("--interval", type=int, default=1800, help="Polling interval in seconds (default: 1800)")
    args = parser.parse_args()

    # Allow CLI override of the webhook for one-off runs
    if args.webhook:
        DISCORD_WEBHOOK_URL = args.webhook

    # Register signal handlers for graceful shutdown
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        # Some platforms may not support SIGTERM
        pass

    run_monitor(run_once=args.once, interval=args.interval, force=args.force)

    # Ensure explicit exit when requested. Use os._exit to avoid lingering
    # non-daemon threads keeping the process alive after a single-run.
    if args.once:
        print("[*] Exiting after one run.")
        sys.stdout.flush()
        os._exit(0)
