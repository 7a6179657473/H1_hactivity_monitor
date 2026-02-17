# monitor.py
# A Python script to monitor HackerOne's Hacktivity feed for new disclosures
# and send notifications to a Discord channel.

import requests
import json
import os
import sys
import time
import argparse

# --- CONFIGURATION ---
# These are the settings you might need to change.

# The endpoint for HackerOne's public GraphQL API.
H1_GRAPHQL_URL = "https://hackerone.com/graphql"

# Your Discord Webhook URL is loaded from an environment variable for security.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- SCRIPT CONSTANTS ---
# These are internal settings that usually don't need to be changed.

# Get the directory where the script is located to ensure the state file is always in the same place.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# The name of the file used to store the ID of the last report we've seen.
STATE_FILE = os.path.join(BASE_DIR, "last_disclosed_id.txt")

# Standard headers to make our script look like a regular web browser when it talks to HackerOne's API.
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

# This is the GraphQL query. It's like a specific API request that asks HackerOne for exactly the data we need:
# the 10 most recent, publicly disclosed reports, ordered by when they were disclosed.
QUERY = """
query {
  reports(
    first: 10,
    where: { disclosed_at: { _is_null: false } },
    order_by: { field: disclosed_at, direction: DESC }
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

# --- FUNCTIONS ---

def sanitize_input(text):
    """
    Strips characters that have special meaning in Discord markdown.
    
    Args:
        text (str): The input string to sanitize.
        
    Returns:
        str: The sanitized string.
    """
    if not isinstance(text, str):
        return text
    # Characters to escape: *, _, `, |, >, ~
    return text.replace('*', '').replace('_', '').replace('`', '').replace('|', '').replace('>', '').replace('~', '')

def fetch_hacktivity():
    """
    Fetches the latest disclosed reports from HackerOne's GraphQL API.
    
    This function sends the QUERY to HackerOne and processes the response.
    It handles potential network errors and API errors.
    
    Returns:
        A list of report objects (as dictionaries), or None if an error occurs.
    """
    print("[*] Fetching latest disclosures from HackerOne...")
    payload = {"query": QUERY}
    try:
        # Send the request to the API.
        response = requests.post(H1_GRAPHQL_URL, json=payload, headers=HEADERS, timeout=10)
        # If the response was an error (like 404 or 500), this will raise an exception.
        response.raise_for_status()
        data = response.json()
        
        # Check if the API itself reported any errors in the data.
        if 'errors' in data:
            print("[!] An error occurred while querying the GraphQL API.")
            return None
            
        # Extract the list of reports from the nested JSON response.
        nodes = data.get("data", {}).get("reports", {}).get("nodes", [])
        return nodes
    except requests.exceptions.RequestException:
        # Handle network-related errors.
        print("[!] A network error occurred while fetching Hacktivity data.")
        return None

def send_to_discord(report):
    """
    Formats a report into a nice-looking Discord embed and sends it via webhook.
    
    Args:
        report (dict): A dictionary containing the details of a single vulnerability report.
    """
    if not report:
        return

    # --- Data Extraction & Sanitization ---
    # Pull out the specific details we want from the report object and sanitize them.
    report_id = report.get("_id")
    title = sanitize_input(report.get("title", "No Title"))
    team = sanitize_input(report.get("team", {}).get("handle", "N/A"))
    
    # Make sure the URL is a full, valid URL.
    raw_url = report.get("url")
    url = raw_url if raw_url and raw_url.startswith("http") else f"https://hackerone.com{raw_url}"
    
    # Safely get the severity rating.
    severity_obj = report.get("severity")
    severity = "N/A"
    if severity_obj and severity_obj.get("rating"):
        severity = severity_obj.get("rating").capitalize()

    # --- Embed Creation ---
    # This dictionary defines the structure and content of the Discord message.
    # It creates a rich "embed" with a title, link, color, and fields.
    embed = {
        "title": f"New Disclosure: {title}",
        "url": url,
        "color": 3447003,  # A nice blue color
        "fields": [
            {"name": "Program", "value": team, "inline": True},
            {"name": "Severity", "value": severity, "inline": True},
            {"name": "Report ID", "value": f"#{report_id}", "inline": True}
        ],
        "footer": {"text": "HackerOne Monitor"}
    }

    payload = {"embeds": [embed]}
    try:
        # Send the formatted payload to the Discord webhook URL.
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status() # Check for errors from Discord's side.
        print(f"[+] Successfully sent report #{report_id} to Discord.")
    except requests.exceptions.RequestException:
        print(f"[!] A network error occurred while sending a notification to Discord for report #{report_id}.")

def get_last_id():
    """
    Reads the last processed report ID from our state file.
    
    This prevents us from sending duplicate notifications every time the script runs.
    
    Returns:
        The last seen report ID as a string, or None if the file doesn't exist.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            content = f.read().strip()
            return content if content else None
    return None

def save_last_id(report_id):
    """
    Saves the ID of the most recent report we've processed to the state file.
    
    Args:
        report_id (str): The ID of the report to save.
    """
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(report_id))
    except IOError as e:
        print(f"[!] Error saving state to {STATE_FILE}: {e}")

def run_monitor(run_once=False):
    """
    The main execution loop for the monitor.
    
    It fetches reports, checks for new ones against the last seen ID,
    sends notifications for new reports, and then updates the last seen ID.
    
    Args:
        run_once (bool): If True, the loop runs only once and then exits.
                         If False, it runs forever, pausing between checks.
    """
    print("[*] Starting HackerOne Hacktivity Monitor...")
    while True:
        nodes = fetch_hacktivity()
        if nodes:
            last_seen_id = get_last_id()
            new_reports = []

            # On the very first run, the state file won't exist.
            # We'll initialize it with the ID of the newest report to avoid
            # spamming the channel with the 10 reports we just fetched.
            if last_seen_id is None:
                print(f"[*] First run detected. Initializing with latest report ID: {nodes[0]['_id']}")
                save_last_id(nodes[0]['_id'])
            else:
                # We have a history, so let's find what's new.
                # Go through the fetched reports one by one.
                for node in nodes:
                    # If we find the report we saw last time, stop. Everything after it is old news.
                    if str(node['_id']) == last_seen_id:
                        break
                    # If it's not the one we last saw, it must be new. Add it to our list.
                    new_reports.append(node)
                
                if new_reports:
                    print(f"[*] Found {len(new_reports)} new reports.")
                    # We process the reports in reverse order (oldest to newest)
                    # so the notifications appear in chronological order in Discord.
                    for report in reversed(new_reports):
                        send_to_discord(report)
                    
                    # After sending all notifications, update the state file to the ID
                    # of the absolute newest report we just handled.
                    save_last_id(new_reports[0]['_id'])
                else:
                    print(f"[*] No new disclosures. (Last known ID: {last_seen_id})")
        else:
            print("[!] No reports found or an API error occurred.")

        # If the --once flag was used, break the loop and exit the script.
        if run_once:
            print("[*] Run complete.")
            break

        # If not running once, wait for 10 minutes before checking again.
        print("[*] Waiting for 10 minutes before the next check...")
        time.sleep(600)

# --- SCRIPT EXECUTION ---

# This is the standard entry point for a Python script.
# The code inside this block only runs when you execute the script directly
# (e.g., `python monitor.py`), not when it's imported into another script.
if __name__ == "__main__":
    # Add a check to ensure the Discord Webhook URL is set.
    if not DISCORD_WEBHOOK_URL:
        print("[!] FATAL: The DISCORD_WEBHOOK_URL environment variable is not set.")
        print("[!] Please set it to your Discord webhook URL.")
        print("[!] Example: export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'")
        sys.exit(1) # Exit with a non-zero status code to indicate an error.

    # Set up the argument parser to handle command-line options.
    parser = argparse.ArgumentParser(description="A script to monitor HackerOne's Hacktivity feed and notify on Discord.")
    # Add an optional argument `--once` that, if present, runs the script just one time.
    parser.add_argument("--once", action="store_true", help="Run the monitor a single time and then exit.")
    args = parser.parse_args()
    
    # Call the main function, passing whether the --once flag was set.
    run_monitor(run_once=args.once)
