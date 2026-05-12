"""
FIFA World Cup 2026 Ticket Price Alert Bot — v2
Features:
- Currency selection (USD, EUR, GBP, AUD, INR, AED, CAD, MXN)
- Per-match specific price tracking (alert on ANY price change, no threshold)
- Full match schedule browser by group/stage
- Official booking links
- Price check every 5 minutes
"""

import os
import json
import time
import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ["BOT_TOKEN"]
CHECK_INTERVAL = 5 * 60   # 5 minutes
DATA_FILE      = "price_data.json"
SOURCE_URL     = "https://www.fifacollect.info/tickets/world-cup-2026/listings"
BOOKING_URL    = "https://www.fifa.com/en/tickets"
COLLECT_URL    = "https://collect.fifa.com/marketplace"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Currencies ────────────────────────────────────────────────────────────────
CURRENCIES = {
    "USD": {"symbol": "$",   "rate": 1.0,   "flag": "🇺🇸"},
    "EUR": {"symbol": "€",   "rate": 0.92,  "flag": "🇪🇺"},
    "GBP": {"symbol": "£",   "rate": 0.79,  "flag": "🇬🇧"},
    "AUD": {"symbol": "A$",  "rate": 1.54,  "flag": "🇦🇺"},
    "INR": {"symbol": "₹",   "rate": 83.5,  "flag": "🇮🇳"},
    "AED": {"symbol": "AED ","rate": 3.67,  "flag": "🇦🇪"},
    "CAD": {"symbol": "C$",  "rate": 1.36,  "flag": "🇨🇦"},
    "MXN": {"symbol": "MX$", "rate": 17.1,  "flag": "🇲🇽"},
}

def convert(usd: float, currency: str) -> str:
    c = CURRENCIES.get(currency, CURRENCIES["USD"])
    v = usd * c["rate"]
    return f"{c['symbol']}{v:,.0f}" if currency == "INR" else f"{c['symbol']}{v:,.2f}"

# ── Match Schedule ────────────────────────────────────────────────────────────
SCHEDULE = [
    # --- Group A ---
    {"date":"Jun 11","time":"3pm CT",  "match":"Mexico vs South Africa",        "venue":"Estadio Azteca, Mexico City",         "group":"A"},
    {"date":"Jun 11","time":"10pm CT", "match":"South Korea vs Czechia",         "venue":"Estadio Akron, Guadalajara",          "group":"A"},
    {"date":"Jun 15","time":"12pm ET", "match":"Czechia vs South Africa",        "venue":"Mercedes-Benz Stadium, Atlanta",      "group":"A"},
    {"date":"Jun 22","time":"9pm CT",  "match":"Mexico vs South Korea",          "venue":"Estadio Akron, Guadalajara",          "group":"A"},
    # --- Group B ---
    {"date":"Jun 12","time":"3pm ET",  "match":"Canada vs Bosnia & Herzegovina", "venue":"BMO Field, Toronto",                  "group":"B"},
    {"date":"Jun 12","time":"9pm ET",  "match":"USA vs Paraguay",                "venue":"SoFi Stadium, Los Angeles",           "group":"B"},
    {"date":"Jun 15","time":"6pm ET",  "match":"Canada vs Qatar",                "venue":"BC Place, Vancouver",                 "group":"B"},
    {"date":"Jun 15","time":"3pm PT",  "match":"Switzerland vs Bosnia",          "venue":"SoFi Stadium, Los Angeles",           "group":"B"},
    # --- Group C ---
    {"date":"Jun 13","time":"6pm ET",  "match":"Brazil vs Morocco",              "venue":"MetLife Stadium, New York/NJ",        "group":"C"},
    {"date":"Jun 16","time":"6pm ET",  "match":"Scotland vs Morocco",            "venue":"Gillette Stadium, Boston",            "group":"C"},
    {"date":"Jun 17","time":"8:30pm ET","match":"Brazil vs Haiti",               "venue":"Lincoln Financial Field, Philadelphia","group":"C"},
    # --- Group D ---
    {"date":"Jun 17","time":"3pm PT",  "match":"USA vs Australia",               "venue":"Lumen Field, Seattle",                "group":"D"},
    {"date":"Jun 17","time":"11pm ET", "match":"Türkiye vs Paraguay",            "venue":"Levi's Stadium, San Francisco",       "group":"D"},
    # --- Group E ---
    {"date":"Jun 18","time":"4pm ET",  "match":"Germany vs Ivory Coast",         "venue":"BMO Field, Toronto",                  "group":"E"},
    {"date":"Jun 18","time":"8pm CT",  "match":"Ecuador vs Curaçao",             "venue":"Arrowhead Stadium, Kansas City",      "group":"E"},
    # --- Group F ---
    {"date":"Jun 18","time":"1pm CT",  "match":"Netherlands vs Sweden",          "venue":"NRG Stadium, Houston",                "group":"F"},
    # --- Group G ---
    {"date":"Jun 16","time":"3pm PT",  "match":"Belgium vs Egypt",               "venue":"Lumen Field, Seattle",                "group":"G"},
    {"date":"Jun 16","time":"9pm ET",  "match":"Iran vs New Zealand",            "venue":"SoFi Stadium, Los Angeles",           "group":"G"},
    # --- Group H ---
    {"date":"Jun 16","time":"12pm ET", "match":"Spain vs Cape Verde",            "venue":"Mercedes-Benz Stadium, Atlanta",      "group":"H"},
    {"date":"Jun 16","time":"6pm ET",  "match":"Saudi Arabia vs Uruguay",        "venue":"Hard Rock Stadium, Miami",            "group":"H"},
    # --- Group I ---
    {"date":"Jun 16","time":"3pm ET",  "match":"France vs Senegal",              "venue":"MetLife Stadium, New York/NJ",        "group":"I"},
    {"date":"Jun 16","time":"6pm ET",  "match":"Iraq vs Norway",                 "venue":"Gillette Stadium, Boston",            "group":"I"},
    # --- Group J ---
    {"date":"Jun 17","time":"9pm CT",  "match":"Argentina vs Algeria",           "venue":"Arrowhead Stadium, Kansas City",      "group":"J"},
    {"date":"Jun 18","time":"12am ET", "match":"Austria vs Jordan",              "venue":"Levi's Stadium, San Francisco",       "group":"J"},
    # --- Group K ---
    {"date":"Jun 18","time":"1pm CT",  "match":"Portugal vs DR Congo",           "venue":"NRG Stadium, Houston",                "group":"K"},
    {"date":"Jun 18","time":"10pm CT", "match":"Uzbekistan vs Colombia",         "venue":"Estadio Azteca, Mexico City",         "group":"K"},
    # --- Group L ---
    {"date":"Jun 18","time":"4pm CT",  "match":"England vs Croatia",             "venue":"AT&T Stadium, Dallas",                "group":"L"},
    {"date":"Jun 18","time":"7pm ET",  "match":"Ghana vs Panama",                "venue":"BMO Field, Toronto",                  "group":"L"},
    # --- Round of 32 ---
    {"date":"Jun 28","time":"3pm ET",  "match":"R32: Runner-up A vs Runner-up B","venue":"SoFi Stadium, Los Angeles",           "group":"R32"},
    {"date":"Jun 29","time":"9pm CT",  "match":"R32: Winner F vs Runner-up C",   "venue":"Estadio BBVA, Monterrey",             "group":"R32"},
    {"date":"Jun 30","time":"1pm ET",  "match":"R32: Runner-up E vs Runner-up I","venue":"AT&T Stadium, Dallas",                "group":"R32"},
    {"date":"Jun 30","time":"5pm ET",  "match":"R32: Winner I vs 3rd C/D/F/G/H", "venue":"MetLife Stadium, New York/NJ",       "group":"R32"},
    # --- Round of 16 ---
    {"date":"Jul 4", "time":"1pm ET",  "match":"R16 (July 4th Special)",         "venue":"NRG Stadium, Houston",                "group":"R16"},
    {"date":"Jul 4", "time":"5pm ET",  "match":"R16 (July 4th Special)",         "venue":"Lincoln Financial Field, Philadelphia","group":"R16"},
    # --- Semi-Finals ---
    {"date":"Jul 14","time":"TBD",     "match":"Semi-Final 1",                   "venue":"MetLife Stadium, New York/NJ",        "group":"SF"},
    {"date":"Jul 15","time":"TBD",     "match":"Semi-Final 2",                   "venue":"AT&T Stadium, Dallas",                "group":"SF"},
    # --- Final ---
    {"date":"Jul 19","time":"TBD",     "match":"⭐ THE FINAL",                   "venue":"MetLife Stadium, New York/NJ",        "group":"FINAL"},
]

GROUPS = ["A","B","C","D","E","F","G","H","I","J","K","L","R32","R16","SF","FINAL"]

# ── Storage ───────────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"prices": {}, "subscribers": [], "user_settings": {}, "specific_alerts": {}}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data: dict, chat_id: int) -> dict:
    key = str(chat_id)
    data.setdefault("user_settings", {}).setdefault(key, {"currency": "USD"})
    return data["user_settings"][key]

# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_prices() -> Optional[dict]:
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Scrape failed: %s", e)
        return None

    soup   = BeautifulSoup(resp.text, "html.parser")
    prices = {}

    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue
        match_text    = cells[0].get_text(strip=True)
        category_text = cells[3].get_text(strip=True)
        face_val_text = cells[4].get_text(strip=True)
        starting_text = cells[7].get_text(strip=True)
        if not match_text or not starting_text:
            continue

        def parse_price(t: str) -> Optional[float]:
            t = t.replace("$", "").replace(",", "").strip()
            token = t.split()[0] if t else ""
            try:
                return float(token)
            except ValueError:
                return None

        price = parse_price(starting_text)
        face  = parse_price(face_val_text)
        if price is None:
            continue
        key = f"{match_text[:40]}|{category_text}"
        prices[key] = {
            "match":      match_text,
            "category":   category_text,
            "price":      price,
            "face_value": face,
            "updated":    datetime.utcnow().isoformat(),
        }

    log.info("Scraped %d listings", len(prices))
    return prices if prices else None

# ── Alert engine ──────────────────────────────────────────────────────────────

async def send_msg(app: Application, chat_id: int, text: str, kb=None):
    try:
        await app.bot.send_message(
            chat_id=chat_id, text=text, parse_mode="HTML",
            reply_markup=kb, disable_web_page_preview=True
        )
    except Exception as e:
        log.error("send_msg %s: %s", chat_id, e)


async def check_and_notify(app: Application):
    log.info("⏱ Price check…")
    data       = load_data()
    old_prices = data.get("prices", {})
    users      = data.get("user_settings", {})
    specific   = data.get("specific_alerts", {})
    subs       = data.get("subscribers", [])

    new_prices = scrape_prices()
    if not new_prices:
        return

    # Detect all changes
    changes = []
    for key, info in new_prices.items():
        old = old_prices.get(key)
        if not old:
            continue
        old_p, new_p = old["price"], info["price"]
        if old_p == new_p:
            continue
        pct = ((new_p - old_p) / old_p) * 100
        changes.append({
            "key": key, "match": info["match"], "category": info["category"],
            "old": old_p, "new": new_p, "pct": pct,
            "dir": "📉 DROP" if pct < 0 else "📈 HIKE",
        })

    if not changes:
        log.info("No changes.")
        data["prices"] = new_prices
        save_data(data)
        return

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    for chat_id in subs:
        uid      = str(chat_id)
        currency = users.get(uid, {}).get("currency", "USD")
        tracked  = specific.get(uid, [])

        # 1) Specific match tracking — alert on EVERY change
        for c in changes:
            # Match against tracked keys (handle truncation)
            if any(c["key"].startswith(t[:len(c["key"])]) or t.startswith(c["key"][:len(t)]) for t in tracked):
                msg = (
                    f"🔔 <b>Tracked Match — Price Changed!</b>\n"
                    f"<i>{now}</i>\n\n"
                    f"{c['dir']} <b>{c['match']}</b> [{c['category']}]\n"
                    f"Previous: {convert(c['old'], currency)}\n"
                    f"New price: <b>{convert(c['new'], currency)}</b>  ({c['pct']:+.1f}%)\n\n"
                    f"🎟 <a href='{COLLECT_URL}'>Buy on FIFA Collect</a>"
                )
                await send_msg(app, chat_id, msg)

        # 2) General broadcast — changes ≥ 2% for non-specifically-tracking users
        if not tracked:
            big = [c for c in changes if abs(c["pct"]) >= 2]
            if big:
                lines = [f"<b>⚽ FIFA WC 2026 Price Alert</b>\n<i>{now}</i>\n"]
                for c in big[:10]:
                    lines.append(
                        f"{c['dir']} <b>{c['match']}</b> [{c['category']}]\n"
                        f"  {convert(c['old'], currency)} → <b>{convert(c['new'], currency)}</b> ({c['pct']:+.1f}%)"
                    )
                lines.append(f"\n🎟 <a href='{COLLECT_URL}'>View All Listings</a>")
                await send_msg(app, chat_id, "\n".join(lines))

    data["prices"] = new_prices
    save_data(data)

# ── Scheduler ─────────────────────────────────────────────────────────────────

def run_scheduler(app: Application, loop: asyncio.AbstractEventLoop):
    while True:
        fut = asyncio.run_coroutine_threadsafe(check_and_notify(app), loop)
        try:
            fut.result(timeout=180)
        except Exception as e:
            log.error("Scheduler: %s", e)
        time.sleep(CHECK_INTERVAL)

# ── Helper: main menu keyboard ────────────────────────────────────────────────

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 Set Currency",   callback_data="menu_currency"),
         InlineKeyboardButton("🎟 Browse Prices",  callback_data="menu_prices")],
        [InlineKeyboardButton("📅 Match Schedule", callback_data="menu_schedule"),
         InlineKeyboardButton("🔔 Track a Match",  callback_data="menu_track")],
        [InlineKeyboardButton("🛒 Buy Tickets",    callback_data="menu_buy"),
         InlineKeyboardButton("📋 My Alerts",      callback_data="menu_myalerts")],
        [InlineKeyboardButton("🔍 Check Now",      callback_data="menu_check"),
         InlineKeyboardButton("❓ Help",           callback_data="menu_help")],
    ])

# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data    = load_data()
    if chat_id not in data["subscribers"]:
        data["subscribers"].append(chat_id)
    get_user(data, chat_id)
    save_data(data)
    await update.message.reply_text(
        "👋 <b>Welcome to FIFA WC 2026 Ticket Alert Bot!</b>\n\n"
        "✅ You're subscribed to price alerts.\n"
        "⏱ Prices are checked every <b>5 minutes</b>.\n\n"
        "Use the menu below to get started:",
        parse_mode="HTML", reply_markup=main_menu_kb(),
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data    = load_data()
    if chat_id in data["subscribers"]:
        data["subscribers"].remove(chat_id)
        save_data(data)
        await update.message.reply_text("🔕 Unsubscribed. Use /start to re-subscribe.")
    else:
        await update.message.reply_text("You're not subscribed. Use /start to subscribe.")


async def show_currency_menu(target, edit=False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇸 USD ($)",    callback_data="cur_USD"),
         InlineKeyboardButton("🇪🇺 EUR (€)",    callback_data="cur_EUR")],
        [InlineKeyboardButton("🇬🇧 GBP (£)",    callback_data="cur_GBP"),
         InlineKeyboardButton("🇦🇺 AUD (A$)",   callback_data="cur_AUD")],
        [InlineKeyboardButton("🇮🇳 INR (₹)",    callback_data="cur_INR"),
         InlineKeyboardButton("🇦🇪 AED",        callback_data="cur_AED")],
        [InlineKeyboardButton("🇨🇦 CAD (C$)",   callback_data="cur_CAD"),
         InlineKeyboardButton("🇲🇽 MXN (MX$)",  callback_data="cur_MXN")],
        [InlineKeyboardButton("« Back",         callback_data="menu_main")],
    ])
    text = "💱 <b>Select your preferred currency</b>\nPrices will display in your chosen currency:"
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_currency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_currency_menu(update.message)


async def show_prices(chat_id: int, target, edit=False):
    data     = load_data()
    prices   = data.get("prices", {})
    currency = get_user(data, chat_id).get("currency", "USD")

    if not prices:
        text = "⏳ No data yet — please wait up to 5 minutes for the first price check."
    else:
        items = sorted(prices.items(), key=lambda x: x[1]["price"])[:12]
        lines = [f"<b>⚽ FIFA WC 2026 — Cheapest 12 Listings ({currency})</b>\n"]
        for _, info in items:
            fv = convert(info["face_value"], currency) if info.get("face_value") else "N/A"
            lines.append(
                f"• <b>{info['match']}</b> [{info['category']}]\n"
                f"  💰 <b>{convert(info['price'], currency)}</b>  (Face value: {fv})"
            )
        lines.append(f"\n🔗 <a href='{COLLECT_URL}'>See all listings on FIFA Collect</a>")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="menu_main")]])
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


async def cmd_prices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_prices(update.effective_chat.id, update.message)


async def show_schedule_groups(target, edit=False):
    rows = []
    row  = []
    for g in GROUPS:
        label = f"Group {g}" if g not in ("R32","R16","SF","FINAL") else g
        row.append(InlineKeyboardButton(label, callback_data=f"sched_{g}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Back", callback_data="menu_main")])
    text = "📅 <b>FIFA WC 2026 — Match Schedule</b>\nSelect a group or stage:"
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_schedule_groups(update.message)


async def show_track_menu(chat_id: int, target, edit=False):
    data   = load_data()
    prices = data.get("prices", {})
    if not prices:
        text = "⏳ Price data not loaded yet. Try again in a minute."
        if edit:
            await target.edit_message_text(text)
        else:
            await target.reply_text(text)
        return

    keys   = list(prices.keys())[:10]
    rows   = []
    for k in keys:
        info  = prices[k]
        label = f"{info['match'][:22]} [{info['category']}]"
        rows.append([InlineKeyboardButton(label, callback_data=f"track_{k[:60]}")])
    rows.append([InlineKeyboardButton("« Back", callback_data="menu_main")])

    text = (
        "🔔 <b>Track a Specific Match</b>\n\n"
        "Pick a match below. You'll be alerted on <b>every price change</b> — no minimum threshold.\n\n"
        "<i>Showing first 10 listings by price.</i>"
    )
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def cmd_track(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_track_menu(update.effective_chat.id, update.message)


async def show_myalerts(chat_id: int, target, edit=False):
    data     = load_data()
    currency = get_user(data, chat_id).get("currency", "USD")
    tracked  = data.get("specific_alerts", {}).get(str(chat_id), [])
    prices   = data.get("prices", {})

    if not tracked:
        text = (
            "📭 <b>No tracked matches</b>\n\n"
            "Use /track (or the main menu) to pick specific matches.\n"
            "You'll get alerted on every price change for those matches."
        )
    else:
        lines = [f"📋 <b>Your Tracked Matches ({currency})</b>\n"]
        for key in tracked:
            info = prices.get(key)
            if info:
                lines.append(
                    f"• <b>{info['match']}</b> [{info['category']}]\n"
                    f"  Current: <b>{convert(info['price'], currency)}</b>"
                )
            else:
                short = key.split("|")[0][:35]
                lines.append(f"• {short} (awaiting data)")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Clear All Tracked", callback_data="clear_alerts")],
        [InlineKeyboardButton("« Back", callback_data="menu_main")],
    ])
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_myalerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_myalerts(update.effective_chat.id, update.message)


async def show_buy(target, edit=False):
    text = (
        "🎟 <b>Where to Buy FIFA WC 2026 Tickets</b>\n\n"
        "1️⃣ <b>Official FIFA Ticket Portal</b> (Primary sales)\n"
        f"👉 <a href='{BOOKING_URL}'>fifa.com/en/tickets</a>\n"
        "<i>Register, create FIFA ID, apply for tickets</i>\n\n"
        "2️⃣ <b>FIFA Collect Marketplace</b> (Official resale)\n"
        f"👉 <a href='{COLLECT_URL}'>collect.fifa.com/marketplace</a>\n"
        "<i>Official digital resale — prices tracked by this bot</i>\n\n"
        "3️⃣ <b>Official Hospitality — On Location</b>\n"
        "👉 <a href='https://fifaworldcup26.hospitality.fifa.com'>fifaworldcup26.hospitality.fifa.com</a>\n"
        "<i>Premium packages: seats + food + hospitality</i>\n\n"
        "4️⃣ <b>StubHub</b> (Secondary market)\n"
        "👉 <a href='https://www.stubhub.com/fifa-world-cup-tickets'>stubhub.com/fifa-world-cup-tickets</a>\n\n"
        "⚠️ <b>Tip:</b> Always use official sources first. "
        "Avoid unofficial sellers to prevent scams."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="menu_main")]])
    if edit:
        await target.edit_message_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    else:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_buy(update.message)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id  = update.effective_chat.id
    data     = load_data()
    currency = get_user(data, chat_id).get("currency", "USD")
    tracked  = len(data.get("specific_alerts", {}).get(str(chat_id), []))
    subbed   = chat_id in data["subscribers"]
    total    = len(data.get("prices", {}))
    last_upd = "Never"
    if data.get("prices"):
        last_upd = next(iter(data["prices"].values())).get("updated", "N/A")

    await update.message.reply_text(
        f"<b>📊 Bot Status</b>\n\n"
        f"Subscribed: {'✅ Yes' if subbed else '❌ No'}\n"
        f"Currency: <b>{currency}</b>\n"
        f"Matches tracked: <b>{tracked}</b>\n"
        f"Listings monitored: <b>{total}</b>\n"
        f"Last check: <b>{last_upd}</b>\n"
        f"Interval: <b>Every 5 minutes</b>",
        parse_mode="HTML",
    )


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Running price check now…")
    await check_and_notify(ctx.application)
    await update.message.reply_text("✅ Done! Any price changes sent to all subscribers.")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>⚽ FIFA WC 2026 Ticket Bot — All Commands</b>\n\n"
        "/start — Subscribe &amp; open main menu\n"
        "/stop — Unsubscribe from alerts\n"
        "/currency — Set your display currency\n"
        "/prices — Show cheapest 12 live listings\n"
        "/schedule — Browse match schedule by group\n"
        "/track — Track a specific match for any price change\n"
        "/myalerts — View &amp; manage your tracked matches\n"
        "/buy — Get official ticket booking links\n"
        "/check — Force an immediate price check now\n"
        "/status — Your subscription &amp; bot status\n"
        "/help — Show this help message\n\n"
        "<i>Prices sourced from FIFA Collect marketplace. Checked every 5 minutes.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ── Callback router ───────────────────────────────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    d       = q.data
    chat_id = q.message.chat_id
    await q.answer()

    data = load_data()

    # Currency selection
    if d.startswith("cur_"):
        cur = d[4:]
        get_user(data, chat_id)["currency"] = cur
        if chat_id not in data["subscribers"]:
            data["subscribers"].append(chat_id)
        save_data(data)
        c = CURRENCIES[cur]
        await q.edit_message_text(
            f"{c['flag']} Currency set to <b>{cur} ({c['symbol'].strip()})</b>\n\n"
            f"All prices will now show in {cur}.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Main Menu", callback_data="menu_main")]]),
        )

    # Schedule group detail
    elif d.startswith("sched_"):
        group   = d[6:]
        matches = [m for m in SCHEDULE if m["group"] == group]
        label   = f"Group {group}" if group not in ("R32","R16","SF","FINAL") else group
        lines   = [f"📅 <b>FIFA WC 2026 — {label}</b>\n"]
        for m in matches:
            lines.append(
                f"⚽ <b>{m['match']}</b>\n"
                f"   📆 {m['date']}  ⏰ {m['time']}\n"
                f"   🏟 {m['venue']}\n"
            )
        lines.append(f"🎟 <a href='{BOOKING_URL}'>Buy tickets on FIFA.com</a>")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back to Schedule", callback_data="menu_schedule"),
             InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
        ])
        await q.edit_message_text("\n".join(lines), parse_mode="HTML",
                                  reply_markup=kb, disable_web_page_preview=True)

    # Track a specific match
    elif d.startswith("track_"):
        key = d[6:]
        uid = str(chat_id)
        data.setdefault("specific_alerts", {}).setdefault(uid, [])
        if chat_id not in data["subscribers"]:
            data["subscribers"].append(chat_id)

        already = any(
            key.startswith(t[:len(key)]) or t.startswith(key[:len(t)])
            for t in data["specific_alerts"][uid]
        )
        if not already:
            data["specific_alerts"][uid].append(key)
            save_data(data)
            prices   = data.get("prices", {})
            full_key = next((k for k in prices if k[:60] == key or key[:60] == k[:60]), None)
            info     = prices.get(full_key) if full_key else None
            currency = get_user(data, chat_id).get("currency", "USD")
            price_line = f"\nCurrent price: <b>{convert(info['price'], currency)}</b>" if info else ""
            await q.edit_message_text(
                f"✅ <b>Match is now being tracked!</b>\n"
                f"You'll receive an alert on <b>every single price change</b> — no minimum.{price_line}\n\n"
                f"Manage tracked matches: /myalerts",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Main Menu", callback_data="menu_main")]]),
            )
        else:
            await q.answer("You're already tracking this match.", show_alert=True)

    # Clear all tracked alerts
    elif d == "clear_alerts":
        data.setdefault("specific_alerts", {})[str(chat_id)] = []
        save_data(data)
        await q.edit_message_text(
            "🗑 All tracked matches cleared.\nUse /track to add new ones.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Main Menu", callback_data="menu_main")]]),
        )

    # Force check
    elif d == "menu_check":
        await q.edit_message_text("🔄 Running price check now…")
        await check_and_notify(ctx.application)
        await q.edit_message_text(
            "✅ Check complete! Any price changes sent to all subscribers.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Main Menu", callback_data="menu_main")]]),
        )

    # Menu routing
    elif d == "menu_main":
        await q.edit_message_text(
            "🏠 <b>Main Menu — FIFA WC 2026 Ticket Bot</b>",
            parse_mode="HTML", reply_markup=main_menu_kb(),
        )
    elif d == "menu_currency":
        await show_currency_menu(q, edit=True)
    elif d == "menu_prices":
        await show_prices(chat_id, q, edit=True)
    elif d == "menu_schedule":
        await show_schedule_groups(q, edit=True)
    elif d == "menu_track":
        await show_track_menu(chat_id, q, edit=True)
    elif d == "menu_buy":
        await show_buy(q, edit=True)
    elif d == "menu_myalerts":
        await show_myalerts(chat_id, q, edit=True)
    elif d == "menu_help":
        await q.edit_message_text(
            "<b>⚽ FIFA WC 2026 Ticket Bot — Commands</b>\n\n"
            "/start — Subscribe &amp; main menu\n"
            "/currency — Set display currency\n"
            "/prices — Cheapest 12 live listings\n"
            "/schedule — Match schedule by group\n"
            "/track — Track specific match\n"
            "/myalerts — Your tracked matches\n"
            "/buy — Official booking links\n"
            "/check — Force price check\n"
            "/status — Bot status\n\n"
            "<i>Prices checked every 5 minutes from FIFA Collect.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="menu_main")]]),
        )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    for cmd, fn in [
        ("start",     cmd_start),
        ("stop",      cmd_stop),
        ("currency",  cmd_currency),
        ("prices",    cmd_prices),
        ("schedule",  cmd_schedule),
        ("track",     cmd_track),
        ("myalerts",  cmd_myalerts),
        ("buy",       cmd_buy),
        ("status",    cmd_status),
        ("check",     cmd_check),
        ("help",      cmd_help),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(callback_handler))

    log.info("FIFA Bot v2 — starting up…")

    async def post_init(application: Application):
        await check_and_notify(application)

    app.post_init = post_init

    def start_scheduler():
        time.sleep(15)
        main_loop = asyncio.get_event_loop()
        run_scheduler(app, main_loop)

    threading.Thread(target=start_scheduler, daemon=True).start()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
