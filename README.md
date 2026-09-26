# H1 Hacktivity Monitor

A Python script that monitors HackerOne's Hacktivity feed for newly disclosed vulnerability reports and sends notifications to a Discord channel via Webhook.

## Features

- Fetches the latest disclosed reports from HackerOne GraphQL API.
- Filter duplicates using a local state file (`last_disclosed_id.txt`).
- Sends a formatted embed to Discord with details: Program, Severity, Report ID, and Title.
- Can be run as a daemon (loop) or as a one-off script (cron mode).

## Prerequisites

- Python 3.x
- A Discord Webhook URL

## Installation

1. Clone the repository.
2. Install dependencies:
   pip install -r requirements.txt

## Configuration

Set the `DISCORD_WEBHOOK_URL` environment variable to your Discord webhook URL.

**Linux / macOS:**
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

**Windows:**
```powershell
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

You can also create a `.env` file in the same directory as the script and add the following line:

```
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

The script will automatically load the environment variable from this file.


## Usage

### Run continuously (Loop every 1 hour)

```bash
python monitor.py
```

### Run once (e.g., for Cron)

```bash
python monitor.py --once
```

## Files

- `monitor.py`: Main script.
- `last_disclosed_id.txt`: Stores the ID of the last processed report to prevent duplicates.
- `monitor.log`: Log file (if output redirection is used).
