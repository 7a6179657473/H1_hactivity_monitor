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
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

You must set the `DISCORD_WEBHOOK_URL` environment variable to your Discord Webhook URL.

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

Alternatively, you can modify the `monitor.py` file (not recommended) but be sure not to commit your webhook URL.

## Usage

### Run continuously (Loop every 10 minutes)

```bash
python monitor.py
```

### Run once (e.g., for Cron)

```bash
python monitor.py --once
```

## Cron setup (run every 30 minutes)

The following assumes you have Python available on the machine where the cron job will run and that the repository is checked out to `/path/to/H1_hactivity_monitor`.

1. Open the crontab editor:

```bash
crontab -e
```

2. Add the following line to run the script every 30 minutes. Adjust the `PYTHON` and `WORKDIR` paths as needed.

```cron
*/30 * * * * cd /path/to/H1_hactivity_monitor && /usr/bin/python3 monitor.py --once >> monitor.log 2>&1
```

Notes:
- `*/30 * * * *` runs the job every 30 minutes.
- `--once` makes the script run a single check and exit so cron controls scheduling.
- `monitor.log` will capture stdout/stderr; rotate logs as needed (e.g., via `logrotate`).

If you need to run this on a Windows machine, use Task Scheduler to create a scheduled task that executes the equivalent PowerShell or Python command every 30 minutes.


## Files

- `monitor.py`: Main script.
- `last_disclosed_id.txt`: Stores the ID of the last processed report to prevent duplicates.
- `monitor.log`: Log file (if output redirection is used).
