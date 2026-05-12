# ⚽ FIFA WC 2026 Ticket Price Alert Bot

A Telegram bot that monitors FIFA World Cup 2026 ticket prices every **30 minutes** and alerts you to drops or hikes.

## Features
- Scrapes live listings from the official FIFA Collect marketplace
- Notifies all subscribers on price changes
- Per-user configurable alert thresholds (e.g. only alert on ≥5% changes)
- `/prices` command shows cheapest 10 current listings
- Manual `/check` command to force an immediate scan

## Commands
| Command | Description |
|---|---|
| `/start` | Subscribe to alerts |
| `/stop` | Unsubscribe |
| `/prices` | Show cheapest 10 listings |
| `/setalert <pct>` | Set threshold, e.g. `/setalert 5` |
| `/check` | Force a manual check now |
| `/status` | Your subscription info |
| `/help` | Help message |

## Deploy to Railway

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.
2. Push this repo to GitHub.
3. Create a **new service** in your Railway project → connect the GitHub repo.
4. Add environment variable: `BOT_TOKEN=<your_token>`
5. Railway will auto-detect Python and run `python bot.py`.

## Local development
```bash
pip install -r requirements.txt
export BOT_TOKEN=your_token_here
python bot.py
```
