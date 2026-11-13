import os
import json
import math
import socket
import time
import threading
import webbrowser
import urllib.request
import http.cookiejar
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs, quote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ==============================================================================
# 0. SETTINGS & 2-MONTH HISTORICAL BACKTEST START (DYNAMIC PORT FOR RENDER.COM)
# ==============================================================================
PORT = int(os.environ.get("PORT", 8080))
BACKTEST_START_DATE = "2026-09-13"
BACKTEST_START_TS = int(datetime.strptime(BACKTEST_START_DATE, "%Y-%m-%d").timestamp())

# --- TELEGRAM SIGNAL SETTINGS ---
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8798596579:AAH_9EVI-Vu9w7DJ8luf25HvpzRnAtbidPY"
TELEGRAM_CHAT_ID = "8080072260"

# ==============================================================================
# 1. FAVORITE WATCHLIST + ALL MARKET CATALOG (FREE LIVE NSE + XM SPOT/CASH)
# ==============================================================================
FAVORITE_SYMBOLS = ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD", "NIFTY", "BANKNIFTY", "SENSEX", "US100", "US30CASH"]

ASSETS = {
    # --- CORE FAVORITES & XM SPOT / CASH ---
    "XAUUSD":      {"cat": "COMMODITY", "name": "Gold Spot (XM)",              "src": "YAHOO",   "ticker": "XAUUSD=X",      "alt": "GC=F",      "step": 10,    "dec": 2},
    "XAGUSD":      {"cat": "COMMODITY", "name": "Silver Spot (XM)",            "src": "YAHOO",   "ticker": "XAGUSD=X",      "alt": "SI=F",      "step": 0.5,   "dec": 3},
    "BTCUSD":      {"cat": "CRYPTO",    "name": "Bitcoin (XM/Spot)",           "src": "BINANCE", "ticker": "BTCUSDT",       "step": 500,   "dec": 2},
    "ETHUSD":      {"cat": "CRYPTO",    "name": "Ethereum (XM/Spot)",          "src": "BINANCE", "ticker": "ETHUSDT",       "step": 50,    "dec": 2},
    "SOLUSD":      {"cat": "CRYPTO",    "name": "Solana (XM/Spot)",            "src": "BINANCE", "ticker": "SOLUSDT",       "step": 5,     "dec": 2},
    "US100":       {"cat": "US_INDEX",  "name": "US100 NASDAQ Cash (XM)",      "src": "YAHOO",   "ticker": "^NDX",          "alt": "NQ=F",      "is_idx": True,  "step": 10,  "dec": 2},
    "US30CASH":    {"cat": "US_CASH",   "name": "US30 Dow Jones Cash (XM)",    "src": "YAHOO",   "ticker": "^DJI",          "alt": "YM=F",      "is_idx": True,  "step": 50,  "dec": 2},
    "US500CASH":   {"cat": "US_CASH",   "name": "US500 S&P 500 Cash (XM)",     "src": "YAHOO",   "ticker": "^GSPC",         "alt": "ES=F",      "is_idx": True,  "step": 25,  "dec": 2},
    "US2000CASH":  {"cat": "US_CASH",   "name": "US2000 Russell Cash (XM)",    "src": "YAHOO",   "ticker": "^RUT",          "alt": "RTY=F",     "is_idx": True,  "step": 10,  "dec": 2},

    # --- XM COMMODITIES & FOREX (SPOT / CFD) ---
    "USOIL":       {"cat": "COMMODITY", "name": "WTI Crude Oil (XM)",          "src": "YAHOO",   "ticker": "CL=F",          "alt": "BZ=F",      "step": 1,     "dec": 2},
    "UKOIL":       {"cat": "COMMODITY", "name": "Brent Crude Oil (XM)",        "src": "YAHOO",   "ticker": "BZ=F",          "alt": "CL=F",      "step": 1,     "dec": 2},
    "NATGAS":      {"cat": "COMMODITY", "name": "Natural Gas (XM)",            "src": "YAHOO",   "ticker": "NG=F",          "step": 0.1,   "dec": 3},
    "COPPER":      {"cat": "COMMODITY", "name": "Copper Spot (XM)",            "src": "YAHOO",   "ticker": "HG=F",          "step": 0.05,  "dec": 3},
    "PLATINUM":    {"cat": "COMMODITY", "name": "Platinum Spot (XM)",          "src": "YAHOO",   "ticker": "PL=F",          "step": 10,    "dec": 2},
    "PALLADIUM":   {"cat": "COMMODITY", "name": "Palladium Spot (XM)",         "src": "YAHOO",   "ticker": "PA=F",          "step": 10,    "dec": 2},
    "EURUSD":      {"cat": "FOREX",     "name": "EUR/USD (XM)",                "src": "YAHOO",   "ticker": "EURUSD=X",      "step": 0.005, "dec": 5},
    "GBPUSD":      {"cat": "FOREX",     "name": "GBP/USD (XM)",                "src": "YAHOO",   "ticker": "GBPUSD=X",      "step": 0.005, "dec": 5},
    "USDJPY":      {"cat": "FOREX",     "name": "USD/JPY (XM)",                "src": "YAHOO",   "ticker": "USDJPY=X",      "step": 0.5,   "dec": 3},
    "USDINR":      {"cat": "FOREX",     "name": "USD/INR Spot",                "src": "YAHOO",   "ticker": "USDINR=X",      "step": 0.25,  "dec": 4},

    # --- ALL INDIAN MARKET INDICES (FREE ZERO-DELAY NSE LIVE) ---
    "NIFTY":       {"cat": "INDIA_IDX", "name": "Nifty 50 Index",              "src": "INDIA",   "ticker": "^NSEI",         "nse": "NIFTY 50",            "oc_sym": "NIFTY",      "is_idx": True, "step": 50,  "dec": 2},
    "BANKNIFTY":   {"cat": "INDIA_IDX", "name": "Bank Nifty Index",            "src": "INDIA",   "ticker": "^NSEBANK",      "nse": "NIFTY BANK",          "oc_sym": "BANKNIFTY",  "is_idx": True, "step": 100, "dec": 2},
    "SENSEX":      {"cat": "INDIA_IDX", "name": "BSE Sensex Index",            "src": "INDIA",   "ticker": "^BSESN",        "nse": None,                  "oc_sym": "SENSEX",     "is_idx": True, "step": 100, "dec": 2},
    "FINNIFTY":    {"cat": "INDIA_IDX", "name": "Nifty Financial Services",    "src": "INDIA",   "ticker": "NIFTY_FIN_SERVICE.NS", "nse": "NIFTY FINANCIAL SERVICES", "oc_sym": "FINNIFTY", "is_idx": True, "step": 50, "dec": 2},
    "MIDCPNIFTY":  {"cat": "INDIA_IDX", "name": "Nifty Midcap Select",         "src": "INDIA",   "ticker": "NIFTY_MID_SELECT.NS",  "nse": "NIFTY MIDCAP SELECT",      "oc_sym": "MIDCPNIFTY","is_idx": True,"step": 25, "dec": 2},
    "INDIAVIX":    {"cat": "INDIA_IDX", "name": "India VIX Volatility",        "src": "INDIA",   "ticker": "^INDIAVIX",     "nse": "INDIA VIX",           "oc_sym": None,         "is_idx": True, "step": 1,   "dec": 2},
    "NIFTYIT":     {"cat": "INDIA_IDX", "name": "Nifty IT Index",              "src": "INDIA",   "ticker": "^CNXIT",        "nse": "NIFTY IT",            "oc_sym": None,         "is_idx": True, "step": 100, "dec": 2},
    "NIFTYAUTO":   {"cat": "INDIA_IDX", "name": "Nifty Auto Index",            "src": "INDIA",   "ticker": "^CNXAUTO",      "nse": "NIFTY AUTO",          "oc_sym": None,         "is_idx": True, "step": 100, "dec": 2},
    "NIFTYPHARMA": {"cat": "INDIA_IDX", "name": "Nifty Pharma Index",          "src": "INDIA",   "ticker": "^CNXPHARMA",    "nse": "NIFTY PHARMA",        "oc_sym": None,         "is_idx": True, "step": 50,  "dec": 2},
    "NIFTYMETAL":  {"cat": "INDIA_IDX", "name": "Nifty Metal Index",           "src": "INDIA",   "ticker": "^CNXMETAL",     "nse": "NIFTY METAL",         "oc_sym": None,         "is_idx": True, "step": 50,  "dec": 2},

    # --- ALL NIFTY 50 & TOP INDIAN STOCKS ---
    "RELIANCE":    {"cat": "INDIA_STK", "name": "Reliance Industries",         "src": "INDIA",   "ticker": "RELIANCE.NS",   "nse": "RELIANCE",   "oc_sym": "RELIANCE",   "is_idx": False, "step": 20, "dec": 2},
    "HDFCBANK":    {"cat": "INDIA_STK", "name": "HDFC Bank Ltd",               "src": "INDIA",   "ticker": "HDFCBANK.NS",   "nse": "HDFCBANK",   "oc_sym": "HDFCBANK",   "is_idx": False, "step": 20, "dec": 2},
    "TCS":         {"cat": "INDIA_STK", "name": "Tata Consultancy Services",   "src": "INDIA",   "ticker": "TCS.NS",        "nse": "TCS",        "oc_sym": "TCS",        "is_idx": False, "step": 50, "dec": 2},
    "INFY":        {"cat": "INDIA_STK", "name": "Infosys Ltd",                 "src": "INDIA",   "ticker": "INFY.NS",       "nse": "INFY",       "oc_sym": "INFY",       "is_idx": False, "step": 20, "dec": 2},
    "ICICIBANK":   {"cat": "INDIA_STK", "name": "ICICI Bank Ltd",              "src": "INDIA",   "ticker": "ICICIBANK.NS",  "nse": "ICICIBANK",  "oc_sym": "ICICIBANK",  "is_idx": False, "step": 20, "dec": 2},
    "BHARTIARTL":  {"cat": "INDIA_STK", "name": "Bharti Airtel Ltd",           "src": "INDIA",   "ticker": "BHARTIARTL.NS", "nse": "BHARTIARTL", "oc_sym": "BHARTIARTL", "is_idx": False, "step": 20, "dec": 2},
    "SBIN":        {"cat": "INDIA_STK", "name": "State Bank of India",         "src": "INDIA",   "ticker": "SBIN.NS",       "nse": "SBIN",       "oc_sym": "SBIN",       "is_idx": False, "step": 10, "dec": 2},
    "LT":          {"cat": "INDIA_STK", "name": "Larsen & Toubro Ltd",         "src": "INDIA",   "ticker": "LT.NS",         "nse": "LT",         "oc_sym": "LT",         "is_idx": False, "step": 50, "dec": 2},
    "ITC":         {"cat": "INDIA_STK", "name": "ITC Ltd",                     "src": "INDIA",   "ticker": "ITC.NS",        "nse": "ITC",        "oc_sym": "ITC",        "is_idx": False, "step": 5,  "dec": 2},
    "HINDUNILVR":  {"cat": "INDIA_STK", "name": "Hindustan Unilever",          "src": "INDIA",   "ticker": "HINDUNILVR.NS", "nse": "HINDUNILVR", "oc_sym": "HINDUNILVR", "is_idx": False, "step": 20, "dec": 2},
    "BAJFINANCE":  {"cat": "INDIA_STK", "name": "Bajaj Finance Ltd",           "src": "INDIA",   "ticker": "BAJFINANCE.NS", "nse": "BAJFINANCE", "oc_sym": "BAJFINANCE", "is_idx": False, "step": 100,"dec": 2},
    "MARUTI":      {"cat": "INDIA_STK", "name": "Maruti Suzuki India",         "src": "INDIA",   "ticker": "MARUTI.NS",     "nse": "MARUTI",     "oc_sym": "MARUTI",     "is_idx": False, "step": 100,"dec": 2},
    "AXISBANK":    {"cat": "INDIA_STK", "name": "Axis Bank Ltd",               "src": "INDIA",   "ticker": "AXISBANK.NS",   "nse": "AXISBANK",   "oc_sym": "AXISBANK",   "is_idx": False, "step": 20, "dec": 2},
    "KOTAKBANK":   {"cat": "INDIA_STK", "name": "Kotak Mahindra Bank",         "src": "INDIA",   "ticker": "KOTAKBANK.NS",  "nse": "KOTAKBANK",  "oc_sym": "KOTAKBANK",  "is_idx": False, "step": 20, "dec": 2},
    "SUNPHARMA":   {"cat": "INDIA_STK", "name": "Sun Pharmaceutical",          "src": "INDIA",   "ticker": "SUNPHARMA.NS",  "nse": "SUNPHARMA",  "oc_sym": "SUNPHARMA",  "is_idx": False, "step": 20, "dec": 2},
    "TITAN":       {"cat": "INDIA_STK", "name": "Titan Company Ltd",           "src": "INDIA",   "ticker": "TITAN.NS",      "nse": "TITAN",      "oc_sym": "TITAN",      "is_idx": False, "step": 50, "dec": 2},
    "TATAMOTORS":  {"cat": "INDIA_STK", "name": "Tata Motors Ltd",             "src": "INDIA",   "ticker": "TATAMOTORS.NS", "nse": "TATAMOTORS", "oc_sym": "TATAMOTORS", "is_idx": False, "step": 10, "dec": 2},
    "NTPC":        {"cat": "INDIA_STK", "name": "NTPC Ltd",                    "src": "INDIA",   "ticker": "NTPC.NS",       "nse": "NTPC",       "oc_sym": "NTPC",       "is_idx": False, "step": 5,  "dec": 2},
    "ONGC":        {"cat": "INDIA_STK", "name": "Oil & Natural Gas Corp",      "src": "INDIA",   "ticker": "ONGC.NS",       "nse": "ONGC",       "oc_sym": "ONGC",       "is_idx": False, "step": 5,  "dec": 2},
    "POWERGRID":   {"cat": "INDIA_STK", "name": "Power Grid Corp",             "src": "INDIA",   "ticker": "POWERGRID.NS",  "nse": "POWERGRID",  "oc_sym": "POWERGRID",  "is_idx": False, "step": 5,  "dec": 2},
    "ULTRACEMCO":  {"cat": "INDIA_STK", "name": "UltraTech Cement",            "src": "INDIA",   "ticker": "ULTRACEMCO.NS", "nse": "ULTRACEMCO", "oc_sym": "ULTRACEMCO", "is_idx": False, "step": 100,"dec": 2},
    "M&M":         {"cat": "INDIA_STK", "name": "Mahindra & Mahindra",         "src": "INDIA",   "ticker": "M&M.NS",        "nse": "M&M",        "oc_sym": "M&M",        "is_idx": False, "step": 20, "dec": 2},
    "HCLTECH":     {"cat": "INDIA_STK", "name": "HCL Technologies",            "src": "INDIA",   "ticker": "HCLTECH.NS",    "nse": "HCLTECH",    "oc_sym": "HCLTECH",    "is_idx": False, "step": 20, "dec": 2},
    "WIPRO":       {"cat": "INDIA_STK", "name": "Wipro Ltd",                   "src": "INDIA",   "ticker": "WIPRO.NS",      "nse": "WIPRO",      "oc_sym": "WIPRO",      "is_idx": False, "step": 10, "dec": 2},
    "ADANIENT":    {"cat": "INDIA_STK", "name": "Adani Enterprises",           "src": "INDIA",   "ticker": "ADANIENT.NS",   "nse": "ADANIENT",   "oc_sym": "ADANIENT",   "is_idx": False, "step": 50, "dec": 2},
    "ADANIPORTS":  {"cat": "INDIA_STK", "name": "Adani Ports & SEZ",           "src": "INDIA",   "ticker": "ADANIPORTS.NS", "nse": "ADANIPORTS", "oc_sym": "ADANIPORTS", "is_idx": False, "step": 20, "dec": 2},
    "ASIANPAINT":  {"cat": "INDIA_STK", "name": "Asian Paints Ltd",            "src": "INDIA",   "ticker": "ASIANPAINT.NS", "nse": "ASIANPAINT", "oc_sym": "ASIANPAINT", "is_idx": False, "step": 50, "dec": 2},
    "COALINDIA":   {"cat": "INDIA_STK", "name": "Coal India Ltd",              "src": "INDIA",   "ticker": "COALINDIA.NS",  "nse": "COALINDIA",  "oc_sym": "COALINDIA",  "is_idx": False, "step": 5,  "dec": 2},
    "BAJAJFINSV":  {"cat": "INDIA_STK", "name": "Bajaj Finserv Ltd",           "src": "INDIA",   "ticker": "BAJAJFINSV.NS", "nse": "BAJAJFINSV", "oc_sym": "BAJAJFINSV", "is_idx": False, "step": 20, "dec": 2},
    "TATASTEEL":   {"cat": "INDIA_STK", "name": "Tata Steel Ltd",              "src": "INDIA",   "ticker": "TATASTEEL.NS",  "nse": "TATASTEEL",  "oc_sym": "TATASTEEL",  "is_idx": False, "step": 5,  "dec": 2},
    "JSWSTEEL":    {"cat": "INDIA_STK", "name": "JSW Steel Ltd",               "src": "INDIA",   "ticker": "JSWSTEEL.NS",   "nse": "JSWSTEEL",   "oc_sym": "JSWSTEEL",   "is_idx": False, "step": 10, "dec": 2},
    "TECHM":       {"cat": "INDIA_STK", "name": "Tech Mahindra Ltd",           "src": "INDIA",   "ticker": "TECHM.NS",      "nse": "TECHM",      "oc_sym": "TECHM",      "is_idx": False, "step": 20, "dec": 2},
    "HINDALCO":    {"cat": "INDIA_STK", "name": "Hindalco Industries",         "src": "INDIA",   "ticker": "HINDALCO.NS",   "nse": "HINDALCO",   "oc_sym": "HINDALCO",   "is_idx": False, "step": 10, "dec": 2},
    "BEL":         {"cat": "INDIA_STK", "name": "Bharat Electronics",          "src": "INDIA",   "ticker": "BEL.NS",        "nse": "BEL",        "oc_sym": "BEL",        "is_idx": False, "step": 5,  "dec": 2},
    "TRENT":       {"cat": "INDIA_STK", "name": "Trent Ltd",                   "src": "INDIA",   "ticker": "TRENT.NS",      "nse": "TRENT",      "oc_sym": "TRENT",      "is_idx": False, "step": 50, "dec": 2},
}

SYMBOL_ALIASES = {
    "GOLD":     ("XAUUSD=X", "Gold Spot (XM)", "COMMODITY", 10, 2, "GC=F"),
    "SILVER":   ("XAGUSD=X", "Silver Spot (XM)", "COMMODITY", 0.5, 3, "SI=F"),
    "CRUDEOIL": ("CL=F", "WTI Crude Oil (XM)", "COMMODITY", 1, 2, "BZ=F"),
    "CRUDE":    ("CL=F", "WTI Crude Oil (XM)", "COMMODITY", 1, 2, "BZ=F"),
    "BRENT":    ("BZ=F", "Brent Crude Oil (XM)", "COMMODITY", 1, 2, "CL=F"),
    "BTC":      ("BTCUSDT", "Bitcoin (XM/Spot)", "CRYPTO", 500, 2, None),
    "ETH":      ("ETHUSDT", "Ethereum (XM/Spot)", "CRYPTO", 50, 2, None),
    "SOL":      ("SOLUSDT", "Solana (XM/Spot)", "CRYPTO", 5, 2, None),
    "NAS100":   ("^NDX", "US100 NASDAQ Cash (XM)", "US_INDEX", 10, 2, "NQ=F"),
    "USTEC":    ("^NDX", "US100 NASDAQ Cash (XM)", "US_INDEX", 10, 2, "NQ=F"),
    "US30":     ("^DJI", "US30 Dow Jones Cash (XM)", "US_CASH", 50, 2, "YM=F"),
    "US500":    ("^GSPC", "US500 S&P 500 Cash (XM)", "US_CASH", 25, 2, "ES=F"),
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA_STORE = {}
OPTION_CHAIN_CACHE = {}
NSE_INDICES_CACHE = {"ts": 0, "map": {}}
SIGNAL_LOCK = {}
HISTORICAL_TRADES = []

yahoo_cj = http.cookiejar.CookieJar()
yahoo_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(yahoo_cj))
yahoo_opener.addheaders = list(BROWSER_HEADERS.items())

nse_cj = http.cookiejar.CookieJar()
nse_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(nse_cj))
nse_opener.addheaders = list(BROWSER_HEADERS.items()) + [("Referer", "https://www.nseindia.com/market-data/live-equity-market")]
NSE_READY = False


def send_telegram_raw(msg_text):
    if not TELEGRAM_ENABLED:
        return
    if not TELEGRAM_BOT_TOKEN or "YOUR_BOT_TOKEN" in TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or "YOUR_CHAT_ID" in TELEGRAM_CHAT_ID:
        return

    def _dispatch():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = json.dumps({
                "chat_id": str(TELEGRAM_CHAT_ID).strip(),
                "text": msg_text,
                "parse_mode": "HTML"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                resp.read()
        except Exception as e:
            print(f"❌ [TELEGRAM ERROR]: {e}")

    threading.Thread(target=_dispatch, daemon=True).start()


def send_telegram_startup():
    msg = (
        f"🚀 <b>PRO TRADINGVIEW & OPTION DESK STARTED</b>
"
        f━━━━━━━━━━━━━━━━━━━━"
"
        f✅ <b>Feeds:</b> Free Zero-Delay NSE Live + XM Spot/Cash"
"
        f⭐ <b>Active Favorites:</b> {', '.join(FAVORITE_SYMBOLS)}"
"
        f🕒 <b>Time:</b> {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}"""
    )
    send_telegram_raw(msg)


def send_telegram_signal(symbol, interval, plan):
    if symbol not in FAVORITE_SYMBOLS:
        return
    emoji = "🟢" if "BUY" in plan["signal"] else "🔴"
    msg = (
        f"{emoji} <b>{plan['signal']}</b> | ⭐ <b>{symbol}</b> ({interval})
"
        f━━━━━━━━━━━━━━━━━━━━"
"
        f📊 <b>Market Regime:</b> {plan.get('regime', 'TRENDING')}"
"
        f💪 <b>Volume Strength:</b> {plan.get('strength', 75)}% ({plan.get('vol_ratio', 1.0)}x Vol)"
"
        f📌 <b>Why Formed:</b> {plan.get('analysis', plan['reason'])}"
"
        f🎯 <b>Entry:</b> <code>{plan['entry']}</code>"
"
        f🛑 <b>Stop Loss:</b> <code>{plan['sl']}</code>"
"
        f✅ <b>TP1:</b> <code>{plan['tp1']}</code> | <b>TP2:</b> <code>{plan['tp2']}</code>"
"
        f🕒 <b>Entry Time:</b> {plan.get('entry_time', datetime.now().strftime('%H:%M:%S'))}"""
    )
    send_telegram_raw(msg)


def get_local_lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if "." in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    if not ips:
        ips.add("127.0.0.1")
    return sorted(ips)


def init_sessions():
    global NSE_READY
    try:
        yahoo_opener.open("https://fc.yahoo.com", timeout=3)
    except Exception:
        pass
    try:
        nse_opener.open("https://www.nseindia.com", timeout=4)
        time.sleep(0.25)
        nse_opener.open("https://www.nseindia.com/option-chain", timeout=4)
        NSE_READY = True
    except Exception:
        NSE_READY = False


def fetch_nse_live_index_map():
    global NSE_READY
    now = time.time()
    if now - NSE_INDICES_CACHE["ts"] < 2.5 and NSE_INDICES_CACHE["map"]:
        return NSE_INDICES_CACHE["map"]
    if not NSE_READY:
        init_sessions()
    try:
        with nse_opener.open("https://www.nseindia.com/api/allIndices", timeout=3.0) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        mp = {}
        for row in j.get("data", []):
            idx_name = str(row.get("index", "")).upper().strip()
            last_val = row.get("last")
            if idx_name and last_val is not None:
                mp[idx_name] = float(last_val)
        if mp:
            NSE_INDICES_CACHE["ts"] = now
            NSE_INDICES_CACHE["map"] = mp
        return mp
    except Exception:
        NSE_READY = False
        return NSE_INDICES_CACHE["map"]


def fetch_nse_live_equity_quote(nse_sym):
    global NSE_READY
    if not NSE_READY:
        init_sessions()
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={quote(nse_sym)}"
        with nse_opener.open(url, timeout=3.0) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        p_info = j.get("priceInfo", {})
        ltp = p_info.get("lastPrice")
        vol = j.get("preOpenMarket", {}).get("totalTradedVolume") or j.get("securityWiseDP", {}).get("quantityTraded")
        if ltp is not None:
            return {"price": float(ltp), "vol": float(vol) if vol else None}
    except Exception:
        NSE_READY = False
    return None


def fetch_ultra_fast_live_tick(symbol):
    meta = ASSETS.get(symbol)
    if not meta:
        return None
    dec = meta["dec"]
    try:
        # 1. Free Zero-Delay NSE Live Feed for Indian Indices & Stocks
        if meta["src"] == "INDIA":
            if meta.get("is_idx") and meta.get("nse"):
                idx_map = fetch_nse_live_index_map()
                val = idx_map.get(meta["nse"].upper())
                if val is not None:
                    return {"price": round(val, dec), "vol": None}
            elif not meta.get("is_idx") and meta.get("nse"):
                eq = fetch_nse_live_equity_quote(meta["nse"])
                if eq and eq.get("price"):
                    return {"price": round(eq["price"], dec), "vol": eq.get("vol")}

        # 2. Real-Time Binance Spot Tick for Crypto (BTC, ETH, SOL)
        if meta["src"] == "BINANCE":
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={meta['ticker']}"
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                j = json.loads(resp.read().decode("utf-8"))
                return {"price": round(float(j["lastPrice"]), dec), "vol": round(float(j.get("volume", 0)), 1)}

        # 3. Direct Spot/Cash Tick for XM Commodities, Forex, US100, US Cash & Backup
        enc = quote(meta["ticker"], safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}?interval=1m&range=1d"
        with yahoo_opener.open(url, timeout=2.2) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        res_meta = j["chart"]["result"][0]["meta"]
        p = res_meta.get("regularMarketPrice")
        v = res_meta.get("regularMarketVolume")
        if p is not None:
            return {"price": round(float(p), dec), "vol": float(v) if v else None}
    except Exception:
        pass
    return None


# ==============================================================================
# 2. FABIO VALENTINI ORDERFLOW ENGINE (WITH REAL-TIME VOLUME METRICS)
# ==============================================================================
def compute_fabio_orderflow_profile(rows, atr, dec):
    window = rows[-36:] if len(rows) >= 36 else rows
    lows = [r["low"] for r in window]
    highs = [r["high"] for r in window]
    min_p, max_p = min(lows), max(highs)
    span = max(max_p - min_p, 1e-6)
    bins = 24
    bin_size = span / bins
    vol_bins = [0.0] * bins

    for r in window:
        rng = max(r["high"] - r["low"], 1e-9)
        eff_v = r["volume"] if r["volume"] > 105.0 else (rng * 1000.0)
        mid = (r["high"] + r["low"] + r["close"]) / 3.0
        b_idx = min(bins - 1, max(0, int((mid - min_p) / bin_size)))
        vol_bins[b_idx] += eff_v

    poc_idx = max(range(bins), key=lambda idx: vol_bins[idx])
    poc_price = round(min_p + (poc_idx + 0.5) * bin_size, dec)

    total_v = sum(vol_bins)
    target_v = total_v * 0.70
    acc_v = vol_bins[poc_idx]
    lo_i, hi_i = poc_idx, poc_idx
    while acc_v < target_v and (lo_i > 0 or hi_i < bins - 1):
        v_up = vol_bins[hi_i + 1] if hi_i + 1 < bins else -1
        v_dn = vol_bins[lo_i - 1] if lo_i - 1 >= 0 else -1
        if v_up >= v_dn and hi_i + 1 < bins:
            hi_i += 1
            acc_v += v_up
        elif lo_i - 1 >= 0:
            lo_i -= 1
            acc_v += v_dn
        else:
            break

    vah = round(min_p + (hi_i + 1) * bin_size, dec)
    val = round(min_p + lo_i * bin_size, dec)

    non_zero_bins = [(i, v) for i, v in enumerate(vol_bins) if 1 <= i <= bins - 2 and v > 0]
    lvn_idx = min(non_zero_bins, key=lambda x: x[1])[0] if non_zero_bins else poc_idx
    lvn_price = round(min_p + (lvn_idx + 0.5) * bin_size, dec)

    max_bin_v = max(vol_bins) if vol_bins else 1.0
    histogram = []
    for b in range(bins):
        p_low = round(min_p + b * bin_size, dec)
        p_high = round(min_p + (b + 1) * bin_size, dec)
        histogram.append({
            "p_low": p_low,
            "p_high": p_high,
            "ratio": round(vol_bins[b] / max(1e-9, max_bin_v), 3),
            "is_poc": (b == poc_idx),
            "is_va": (lo_i <= b <= hi_i),
            "is_lvn": (b == lvn_idx),
        })

    prev_win = rows[-46:-10] if len(rows) >= 46 else window[:-3]
    prev_poc = sum((r["high"] + r["low"] + r["close"]) / 3.0 for r in prev_win) / max(1, len(prev_win))

    cur = rows[-1]
    last_close = cur["close"]

    if last_close > vah and poc_price >= prev_poc:
        value_state = "MIGRATING UP 🟢"
        in_cage = False
    elif last_close < val and poc_price <= prev_poc:
        value_state = "MIGRATING DOWN 🔴"
        in_cage = False
    else:
        value_state = "THE CAGE (CHOP) ⚠️"
        in_cage = True

    eff_vols = [(r["volume"] if r["volume"] > 105.0 else (max(r["high"] - r["low"], 1e-9) * 1000.0)) for r in window]
    avg_vol = sum(eff_vols) / max(1, len(eff_vols))
    cur_rng = max(cur["high"] - cur["low"], 1e-9)
    cur_vol = cur["volume"] if cur["volume"] > 105.0 else (cur_rng * 1000.0)
    vol_ratio = round(cur_vol / max(1e-9, avg_vol), 2)

    upper_wick = (cur["high"] - max(cur["open"], cur["close"])) / cur_rng
    lower_wick = (min(cur["open"], cur["close"]) - cur["low"]) / cur_rng

    absorption = "NONE"
    if vol_ratio >= 1.25 and upper_wick >= 0.45 and cur["close"] <= cur["open"]:
        absorption = "BUYERS ABSORBED 🔴"
    elif vol_ratio >= 1.25 and lower_wick >= 0.45 and cur["close"] >= cur["open"]:
        absorption = "SELLERS ABSORBED 🟢"

    price_exp = abs(cur["close"] - cur["open"]) / (atr + 1e-9)
    if price_exp >= 0.95 and vol_ratio <= 1.35:
        effort_model = "THIN BOOK BLAST 🚀"
    elif price_exp < 0.35 and vol_ratio >= 1.40:
        effort_model = "HEAVY ABSORPTION 🧱"
    else:
        effort_model = "BALANCED FLOW"

    delta_pct = round(((cur["close"] - cur["low"]) / cur_rng) * 100.0, 1)

    return {
        "vah": vah, "poc": poc_price, "val": val, "lvn": lvn_price,
        "histogram": histogram, "in_cage": in_cage, "value_state": value_state,
        "absorption": absorption, "effort_model": effort_model,
        "delta_pct": delta_pct, "cur_vol": round(cur_vol, 1), "avg_vol": round(avg_vol, 1), "vol_ratio": vol_ratio,
    }


# ==============================================================================
# 3. SMART MONEY CONCEPTS (BULL/BEAR ORDER BLOCKS & LIQUIDITY SWEEPS)
# ==============================================================================
def compute_smc_features(rows, atr, dec):
    n = len(rows)
    cur = rows[-1]
    last_close, last_high, last_low = cur["close"], cur["high"], cur["low"]

    hist_window = rows[-24:-2] if n >= 24 else (rows[:-1] if n >= 4 else rows)
    swing_high = max(r["high"] for r in hist_window) if hist_window else rows[0]["high"]
    swing_low = min(r["low"] for r in hist_window) if hist_window else rows[0]["low"]
    prior_up = hist_window[-1]["close"] >= hist_window[0]["open"] if hist_window else True

    if last_close > swing_high:
        structure = "BULL BOS" if prior_up else "BULL CHoCH"
    elif last_close < swing_low:
        structure = "BEAR BOS" if not prior_up else "BEAR CHoCH"
    else:
        structure = "BULL STRUCT" if last_close >= (swing_high + swing_low) / 2.0 else "BEAR STRUCT"

    recent_3 = rows[-3:]
    cur_rng = max(cur["high"] - cur["low"], 1e-9)
    lower_wick_pct = (min(cur["open"], cur["close"]) - cur["low"]) / cur_rng
    upper_wick_pct = (cur["high"] - max(cur["open"], cur["close"])) / cur_rng

    sweep = "NONE"
    if any(r["high"] > swing_high for r in recent_3) and last_close < swing_high:
        sweep = "PDH SWEPT 🔴"
    elif any(r["low"] < swing_low for r in recent_3) and last_close > swing_low:
        sweep = "PDL SWEPT 🟢"

    bull_ob, bear_ob, bull_ob_idx, bear_ob_idx = None, None, 0, 0
    for i in range(n - 3, 1, -1):
        c_prev, c_next = rows[i], rows[i + 1]
        impulse = abs(c_next["close"] - c_next["open"])
        if bull_ob is None and c_prev["close"] < c_prev["open"] and c_next["close"] > c_next["open"] and impulse >= atr * 0.85:
            if last_close >= c_prev["low"]:
                bull_ob = [round(c_prev["low"], dec), round(c_prev["high"], dec)]
                bull_ob_idx = i
        if bear_ob is None and c_prev["close"] > c_prev["open"] and c_next["close"] < c_next["open"] and impulse >= atr * 0.85:
            if last_close <= c_prev["high"]:
                bear_ob = [round(c_prev["low"], dec), round(c_prev["high"], dec)]
                bear_ob_idx = i
        if bull_ob and bear_ob:
            break

    smc_trigger = "NEUTRAL"
    if sweep == "PDL SWEPT 🟢" and cur["close"] > cur["open"] and lower_wick_pct >= 0.35:
        smc_trigger = "PDL TRAP SWEEP"
    elif sweep == "PDH SWEPT 🔴" and cur["close"] < cur["open"] and upper_wick_pct >= 0.35:
        smc_trigger = "PDH TRAP SWEEP"
    elif bull_ob and (bull_ob[0] * 0.999 <= last_low <= bull_ob[1] * 1.002) and last_close > cur["open"]:
        smc_trigger = "BULL OB BOUNCE"
    elif bear_ob and (bear_ob[0] * 0.998 <= last_high <= bear_ob[1] * 1.001) and last_close < cur["open"]:
        smc_trigger = "BEAR OB REJECT"

    latest_day = datetime.fromtimestamp(rows[-1]["time"]).strftime("%Y-%m-%d")
    prev_days = sorted(list({datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") for r in rows if datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") < latest_day}))
    pdh, pdl, ppoc = None, None, None
    if prev_days:
        p_day = prev_days[-1]
        p_rows = [r for r in rows if datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") == p_day]
        if p_rows:
            pdh = round(max(r["high"] for r in p_rows), dec)
            pdl = round(min(r["low"] for r in p_rows), dec)
            ppoc = round(sum((r["high"] + r["low"] + r["close"]) / 3.0 for r in p_rows) / len(p_rows), dec)

    return {
        "structure": structure, "sweep": sweep, "bull_ob": bull_ob, "bear_ob": bear_ob,
        "bull_ob_idx": bull_ob_idx, "bear_ob_idx": bear_ob_idx, "smc_trigger": smc_trigger,
        "pdh": pdh, "pdl": pdl, "ppoc": ppoc,
    }


# ==============================================================================
# 4. OPTION CHAIN, MAX PAIN & BLACK-SCHOLES GREEKS ENGINE
# ==============================================================================
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def calc_bs_greeks(spot, strike, t_years, iv_pct, r=0.065):
    S, K = max(spot, 1e-6), max(strike, 1e-6)
    T = max(t_years, 1.0 / 365.0)
    sigma = max(iv_pct / 100.0, 0.05)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    nd1, nd2 = norm_cdf(d1), norm_cdf(d2)
    pdf_d1 = norm_pdf(d1)
    ce_price = S * nd1 - K * math.exp(-r * T) * nd2
    pe_price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    ce_theta = (-(S * pdf_d1 * sigma) / (2.0 * math.sqrt(T)) - r * K * math.exp(-r * T) * nd2) / 365.0
    return {
        "ce_ltp": round(max(0.05, ce_price), 2), "pe_ltp": round(max(0.05, pe_price), 2),
        "ce_delta": round(nd1, 2), "pe_delta": round(nd1 - 1.0, 2),
        "gamma": round(gamma, 5), "ce_theta": round(ce_theta, 2),
    }


def classify_institutional_buildup(price_chg, oi_chg):
    if price_chg >= 0 and oi_chg > 0:
        return "LONG BUILDUP 🟢"
    if price_chg < 0 and oi_chg > 0:
        return "SHORT BUILDUP 🔴"
    if price_chg >= 0 and oi_chg < 0:
        return "SHORT COVERING 🚀"
    if price_chg < 0 and oi_chg < 0:
        return "LONG UNWINDING ⚠️"
    return "NEUTRAL"


def compute_max_pain(strikes_list):
    if not strikes_list:
        return 0
    best_strike = strikes_list[0]["strike"]
    min_pain = float("inf")
    for cand in strikes_list:
        k_test = cand["strike"]
        pain = 0.0
        for row in strikes_list:
            k = row["strike"]
            if k_test > k:
                pain += (k_test - k) * row["ce_oi"]
            elif k_test < k:
                pain += (k - k_test) * row["pe_oi"]
        if pain < min_pain:
            min_pain = pain
            best_strike = k_test
    return best_strike


def fetch_live_nse_strike_chain(oc_sym, spot_price, is_idx=True):
    global NSE_READY
    now = time.time()
    cached = OPTION_CHAIN_CACHE.get(f"CHAIN_{oc_sym}")
    if cached and (now - cached["ts"] < 25):
        return cached["data"]
    if not NSE_READY:
        init_sessions()
    endpoint = "option-chain-indices" if is_idx else "option-chain-equities"
    url = f"https://www.nseindia.com/api/{endpoint}?symbol={quote(oc_sym)}"
    try:
        with nse_opener.open(url, timeout=4.5) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        data_rows = j.get("records", {}).get("data", [])
        if not data_rows:
            return None
        sorted_rows = sorted(data_rows, key=lambda x: abs(x.get("strikePrice", 0) - spot_price))[:15]
        sorted_rows.sort(key=lambda x: x.get("strikePrice", 0))
        strikes_out, tot_ce_oi, tot_pe_oi, max_ce_oi, max_pe_oi, call_wall, put_wall = [], 0, 0, 0, 0, 0, 0
        for item in sorted_rows:
            k = item.get("strikePrice", 0)
            ce, pe = item.get("CE") or {}, item.get("PE") or {}
            ce_oi, pe_oi = int(ce.get("openInterest", 0) or 0), int(pe.get("openInterest", 0) or 0)
            ce_chg, pe_chg = int(ce.get("changeinOpenInterest", 0) or 0), int(pe.get("changeinOpenInterest", 0) or 0)
            ce_pchg, pe_pchg = float(ce.get("change", 0) or 0), float(pe.get("change", 0) or 0)
            iv = float(ce.get("impliedVolatility") or pe.get("impliedVolatility") or 16.0)
            greeks = calc_bs_greeks(spot_price, k, 5.0 / 365.0, iv)
            ce_ltp = float(ce.get("lastPrice", 0) or 0) or greeks["ce_ltp"]
            pe_ltp = float(pe.get("lastPrice", 0) or 0) or greeks["pe_ltp"]
            tot_ce_oi += ce_oi
            tot_pe_oi += pe_oi
            if ce_oi > max_ce_oi and k >= spot_price:
                max_ce_oi, call_wall = ce_oi, k
            if pe_oi > max_pe_oi and k <= spot_price:
                max_pe_oi, put_wall = pe_oi, k
            strikes_out.append({
                "strike": k,
                "is_atm": abs(k - spot_price) == min(abs(x.get("strikePrice", 0) - spot_price) for x in sorted_rows),
                "ce_oi": ce_oi, "ce_chg": ce_chg, "ce_ltp": round(ce_ltp, 2), "ce_iv": round(iv, 1),
                "ce_delta": greeks["ce_delta"], "ce_gamma": greeks["gamma"], "ce_theta": greeks["ce_theta"],
                "ce_act": classify_institutional_buildup(ce_pchg, ce_chg),
                "pe_oi": pe_oi, "pe_chg": pe_chg, "pe_ltp": round(pe_ltp, 2),
                "pe_delta": greeks["pe_delta"], "pe_act": classify_institutional_buildup(pe_pchg, pe_chg),
            })
        pcr = round(tot_pe_oi / max(1, tot_ce_oi), 2)
        res = {
            "source": "LIVE NSE OC", "pcr": pcr,
            "max_pain": compute_max_pain(strikes_out),
            "call_wall": call_wall or sorted_rows[-2]["strikePrice"],
            "put_wall": put_wall or sorted_rows[1]["strikePrice"],
            "strikes": strikes_out,
        }
        OPTION_CHAIN_CACHE[f"CHAIN_{oc_sym}"] = {"ts": now, "data": res}
        return res
    except Exception:
        NSE_READY = False
        return None


def build_option_chain_profile(symbol, meta, rows, atr, dec, is_backtest=False):
    last_close = rows[-1]["close"]
    prev_close = rows[-2]["close"] if len(rows) >= 2 else last_close
    price_chg = last_close - prev_close

    if not is_backtest and meta["src"] == "INDIA" and meta.get("oc_sym") and meta["oc_sym"] != "SENSEX":
        live_nse = fetch_live_nse_strike_chain(meta["oc_sym"], last_close, meta.get("is_idx", True))
        if live_nse and live_nse.get("strikes"):
            return live_nse

    step = meta.get("step", 10)
    atm_strike = round(last_close / step) * step
    ann_iv = round(max(12.0, min(85.0, (atr / max(last_close, 1e-6)) * math.sqrt(252) * 100.0)), 1)
    recent = rows[-15:]
    put_p, call_p = 0.0, 0.0
    for idx_r, r in enumerate(recent):
        w = 1.0 + (idx_r / len(recent)) * 1.5
        rng = max(r["high"] - r["low"], 1e-9)
        ev = (r["volume"] if r["volume"] > 105.0 else (rng * 1000.0)) * w
        cp = (r["close"] - r["low"]) / rng
        put_p += ev * cp
        call_p += ev * (1.0 - cp)
    pcr = round(put_p / max(1e-9, call_p), 2)

    strikes_out = []
    for offset in range(-7, 8):
        k = round(atm_strike + offset * step, dec)
        g = calc_bs_greeks(last_close, k, 7.0 / 365.0, ann_iv)
        dist_f = math.exp(-0.18 * (offset ** 2))
        ce_bias = 1.35 if offset >= 2 else (0.75 if offset <= -2 else 1.0)
        pe_bias = 1.35 if offset <= -2 else (0.75 if offset >= 2 else 1.0)
        ce_chg = int((-1200) if (price_chg > 0 and offset in (0, 1)) else 900)
        pe_chg = int((-1200) if (price_chg < 0 and offset in (0, -1)) else 900)
        strikes_out.append({
            "strike": k, "is_atm": (offset == 0),
            "ce_oi": int(12000 * dist_f * ce_bias + 1500), "ce_chg": ce_chg, "ce_ltp": g["ce_ltp"], "ce_iv": ann_iv,
            "ce_delta": g["ce_delta"], "ce_gamma": g["gamma"], "ce_theta": g["ce_theta"],
            "ce_act": classify_institutional_buildup(price_chg, ce_chg),
            "pe_oi": int(12000 * dist_f * pe_bias + 1500), "pe_chg": pe_chg, "pe_ltp": g["pe_ltp"],
            "pe_delta": g["pe_delta"], "pe_act": classify_institutional_buildup(-price_chg, pe_chg),
        })

    return {
        "source": "BS GREEKS + OI FLOW",
        "pcr": pcr,
        "max_pain": compute_max_pain(strikes_out),
        "call_wall": round(atm_strike + step * 2, dec),
        "put_wall": round(atm_strike - step * 2, dec),
        "strikes": strikes_out,
    }


# ==============================================================================
# 5. MARKET DATA FETCHERS (FULL 2 MONTHS / 60 DAYS HISTORICAL CANDLES)
# ==============================================================================
def aggregate_candles(rows, factor):
    if factor <= 1 or len(rows) < factor:
        return rows
    agg = []
    for i in range(0, len(rows) - factor + 1, factor):
        chunk = rows[i:i + factor]
        agg.append({
            "time": chunk[0]["time"],
            "open": chunk[0]["open"],
            "high": max(x["high"] for x in chunk),
            "low": min(x["low"] for x in chunk),
            "close": chunk[-1]["close"],
            "volume": sum(x["volume"] for x in chunk),
        })
    return agg


def fetch_binance_klines(ticker, interval="15m", limit=900, start_ms=None):
    tf_map = {
        "1m": ("1m", 1), "3m": ("3m", 1), "5m": ("5m", 1),
        "15m": ("15m", 1), "30m": ("30m", 1), "45m": ("15m", 3),
        "1h": ("1h", 1), "2h": ("2h", 1), "3h": ("1h", 3), "4h": ("4h", 1),
        "1d": ("1d", 1), "1w": ("1w", 1), "1M": ("1M", 1)
    }
    bn_tf, mult = tf_map.get(interval, ("15m", 1))
    req_limit = min(1000, limit * mult)
    qs_extra = f"&startTime={start_ms}" if start_ms else ""
    for url in [
        f"https://api.binance.com/api/v3/klines?symbol={ticker}&interval={bn_tf}&limit={req_limit}{qs_extra}",
        f"https://data-api.binance.vision/api/v3/klines?symbol={ticker}&interval={bn_tf}&limit={req_limit}{qs_extra}",
    ]:
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) >= 4:
                raw = [{"time": int(k[0] // 1000), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]
                return aggregate_candles(raw, mult)[-limit:]
        except Exception:
            continue
    return []


def fetch_yahoo_multi_mirror(ticker, interval="15m", custom_range=None, max_rows=1800):
    # Upgraded to 60d (2 Months) history across intraday timeframes
    tf_map = {
        "1m": ("1m", "7d", 1),   "3m": ("2m", "15d", 1),  "5m": ("5m", "60d", 1),
        "15m": ("15m", "60d", 1),"30m": ("30m", "60d", 1),"45m": ("15m", "60d", 3),
        "1h": ("60m", "60d", 1), "2h": ("60m", "60d", 2), "3h": ("60m", "60d", 3),
        "4h": ("60m", "60d", 4), "1d": ("1d", "1y", 1),   "1w": ("1wk", "2y", 1), "1M": ("1mo", "5y", 1)
    }
    y_int, y_range, mult = tf_map.get(interval, ("15m", "60d", 1))
    if custom_range:
        y_range = custom_range
    enc = quote(ticker, safe="")
    for url in [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}?interval={y_int}&range={y_range}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{enc}?interval={y_int}&range={y_range}",
    ]:
        try:
            with yahoo_opener.open(url, timeout=5.0) as resp:
                j = json.loads(resp.read().decode("utf-8"))
            res = j["chart"]["result"][0]
            ts, q = res["timestamp"], res["indicators"]["quote"][0]
            rows = []
            for i in range(len(ts)):
                if q["open"][i] is None or q["close"][i] is None:
                    continue
                rows.append({"time": int(ts[i]), "open": float(q["open"][i]), "high": float(q["high"][i]), "low": float(q["low"][i]), "close": float(q["close"][i]), "volume": float(q["volume"][i] or 100.0)})
            if len(rows) >= 4:
                agg = aggregate_candles(rows, mult)
                return agg[-max_rows:] if max_rows else agg
        except Exception:
            continue
    return []


def fetch_candles_for_asset(meta, interval="15m"):
    if meta["src"] == "BINANCE":
        return fetch_binance_klines(meta["ticker"], interval, limit=900)
    rows = fetch_yahoo_multi_mirror(meta["ticker"], interval)
    if len(rows) < 4 and meta.get("alt"):
        rows = fetch_yahoo_multi_mirror(meta["alt"], interval)
    return rows


# ==============================================================================
# 6. VOLUME-WEIGHTED SIGNAL STRENGTH & TREND REGIME ENGINE (POINTS 3, 4 & 8)
# ==============================================================================
def detect_market_regime(rows, vwap_val):
    closes = [r["close"] for r in rows[-30:]]
    if len(closes) < 10:
        return "RANGING"
    ema9 = sum(closes[-9:]) / 9.0
    ema21 = sum(closes[-21:]) / min(21, len(closes))
    last_c = closes[-1]
    if last_c > ema9 > ema21 and last_c > vwap_val:
        return "BULLISH TREND 🟢"
    elif last_c < ema9 < ema21 and last_c < vwap_val:
        return "BEARISH TREND 🔴"
    return "RANGING / CHOP ⚠️"


def evaluate_unified_confluence(fabio, smc, oc, rows, vwap_val, atr, dec):
    cur = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else cur
    last_close = cur["close"]
    regime = detect_market_regime(rows, vwap_val)
    vol_ratio = fabio.get("vol_ratio", 1.0)
    delta_pct = fabio.get("delta_pct", 50.0)

    buy_trigger = round(max(fabio["vah"], vwap_val, prev["high"]) + atr * 0.12, dec)
    sell_trigger = round(min(fabio["val"], vwap_val, prev["low"]) - atr * 0.12, dec)

    # Calculate Bullish & Bearish Volume-Backed Signal Strength (0-100%)
    bull_score = 0
    bull_reasons = []
    if "BULLISH" in regime:
        bull_score += 25
        bull_reasons.append("Bullish Trend Regime")
    if (not fabio["in_cage"]) and ("UP" in fabio["value_state"]) and last_close > fabio["vah"]:
        bull_score += 25
        bull_reasons.append("Value Area Migration UP")
    if fabio["absorption"] == "SELLERS ABSORBED 🟢":
        bull_score += 20
        bull_reasons.append("Sellers Absorbed at Low")
    if smc["smc_trigger"] in ("PDL TRAP SWEEP", "BULL OB BOUNCE"):
        bull_score += 20
        bull_reasons.append(smc["smc_trigger"])
    if vol_ratio >= 1.25 and delta_pct >= 60.0:
        bull_score += 20
        bull_reasons.append(f"High Buy Vol ({vol_ratio}x, Delta {delta_pct}%)")
    elif vol_ratio >= 1.05 and delta_pct >= 55.0:
        bull_score += 10
    if oc["pcr"] >= 1.10:
        bull_score += 10
        bull_reasons.append(f"Bullish PCR ({oc['pcr']})")
    bull_score = min(99, bull_score)

    bear_score = 0
    bear_reasons = []
    if "BEARISH" in regime:
        bear_score += 25
        bear_reasons.append("Bearish Trend Regime")
    if (not fabio["in_cage"]) and ("DOWN" in fabio["value_state"]) and last_close < fabio["val"]:
        bear_score += 25
        bear_reasons.append("Value Area Migration DOWN")
    if fabio["absorption"] == "BUYERS ABSORBED 🔴":
        bear_score += 20
        bear_reasons.append("Buyers Absorbed at High")
    if smc["smc_trigger"] in ("PDH TRAP SWEEP", "BEAR OB REJECT"):
        bear_score += 20
        bear_reasons.append(smc["smc_trigger"])
    if vol_ratio >= 1.25 and delta_pct <= 40.0:
        bear_score += 20
        bear_reasons.append(f"High Sell Vol ({vol_ratio}x, Delta {delta_pct}%)")
    elif vol_ratio >= 1.05 and delta_pct <= 45.0:
        bear_score += 10
    if oc["pcr"] <= 0.90:
        bear_score += 10
        bear_reasons.append(f"Bearish PCR ({oc['pcr']})")
    bear_score = min(99, bear_score)

    # Strict Market Regime + Volume Confirmation Filter (Prevents counter-trend weak signals)
    bull_ok = (
        bull_score >= 65
        and ("BEARISH" not in regime)
        and vol_ratio >= 1.05
        and cur["close"] > cur["open"]
        and last_close > vwap_val
        and last_close < (oc["call_wall"] - atr * 1.1)
    )

    bear_ok = (
        bear_score >= 65
        and ("BULLISH" not in regime)
        and vol_ratio >= 1.05
        and cur["close"] < cur["open"]
        and last_close < vwap_val
        and last_close > (oc["put_wall"] + atr * 1.1)
    )

    if bull_ok:
        entry = round(last_close, dec)
        ob_floor = smc["bull_ob"][0] if smc["bull_ob"] else fabio["val"]
        sl = round(min(cur["low"], ob_floor, last_close - atr * 1.1), dec)
        risk = max(abs(entry - sl), atr * 0.7)
        analysis_txt = " + ".join(bull_reasons[:3]) or "Institutional Bull Confluence"
        return {
            "dir": "BUY", "signal": f"STRONG BUY ({bull_score}%)",
            "strength": bull_score, "regime": regime,
            "vol_ratio": vol_ratio, "delta_pct": delta_pct,
            "reason": f
{analysis_txt}",
            "analysis": f"[{regime}] {analysis_txt}. Volume at {vol_ratio}x avg confirms institutional buying above VWAP ({vwap_val}).",
            "entry": entry, "sl": sl,
            "tp1": round(entry + risk * 1.2, dec),
            "tp2": round(max(entry + risk * 2.5, oc["call_wall"]), dec),
            "tp3": round(entry + risk * 4.0, dec),
            "buy_trigger": buy_trigger, "sell_trigger": sell_trigger,
        }

    if bear_ok:
        entry = round(last_close, dec)
        ob_ceil = smc["bear_ob"][1] if smc["bear_ob"] else fabio["vah"]
        sl = round(max(cur["high"], ob_ceil, last_close + atr * 1.1), dec)
        risk = max(abs(sl - entry), atr * 0.7)
        analysis_txt = " + ".join(bear_reasons[:3]) or "Institutional Bear Confluence"
        return {
            "dir": "SELL", "signal": f"STRONG SELL ({bear_score}%)",
            "strength": bear_score, "regime": regime,
            "vol_ratio": vol_ratio, "delta_pct": delta_pct,
            "reason": f"{analysis_txt}",
            "analysis": f"[{regime}] {analysis_txt}. Volume at {vol_ratio}x avg confirms institutional selling below VWAP ({vwap_val}).",
            "entry": entry, "sl": sl,
            "tp1": round(entry - risk * 1.2, dec),
            "tp2": round(min(entry - risk * 2.5, oc["put_wall"]), dec),
            "tp3": round(entry - risk * 4.0, dec),
            "buy_trigger": buy_trigger, "sell_trigger": sell_trigger,
        }

    dom_strength = max(bull_score, bear_score)
    return {
        "dir": "WAIT", "strength": dom_strength, "regime": regime,
        "vol_ratio": vol_ratio, "delta_pct": delta_pct,
        "analysis": f"[{regime}] Strength {dom_strength}% (Need >=65% + Vol >=1.05x). Waiting for breakout > {buy_trigger} or breakdown < {sell_trigger}.",
        "buy_trigger": buy_trigger, "sell_trigger": sell_trigger
    }


# ==============================================================================
# 7. 2-MONTH BACKTESTER & ALL-ASSETS WIN RATIO STORE
# ==============================================================================
def run_backtest_for_symbol(sym, meta):
    dec = meta["dec"]
    if meta["src"] == "BINANCE":
        p1 = fetch_binance_klines(meta["ticker"], interval="30m", limit=1000, start_ms=BACKTEST_START_TS * 1000)
        p2 = fetch_binance_klines(meta["ticker"], interval="30m", limit=1000, start_ms=(p1[-1]["time"] + 1800) * 1000) if p1 else []
        rows = p1 + p2
    else:
        rows = fetch_yahoo_multi_mirror(meta["ticker"], interval="30m", custom_range="60d", max_rows=2500)
        if len(rows) < 40 and meta.get("alt"):
            rows = fetch_yahoo_multi_mirror(meta["alt"], interval="30m", custom_range="60d", max_rows=2500)

    if len(rows) < 35:
        return []

    trades, active_trade = [], None
    for idx in range(30, len(rows)):
        cur = rows[idx]
        if cur["time"] < BACKTEST_START_TS:
            continue

        if active_trade:
            r_pts = abs(active_trade["entry"] - active_trade["orig_sl"])
            if active_trade["dir"] == "BUY":
                if cur["high"] >= active_trade["entry"] + r_pts * 0.6:
                    active_trade["sl"] = max(active_trade["sl"], active_trade["entry"])
                if cur["high"] >= active_trade["tp1"]:
                    active_trade["outcome"] = "WIN"
                    active_trade["status"] = "TP3 MAX 🔥" if cur["high"] >= active_trade["tp3"] else ("TP2 HIT 🎯" if cur["high"] >= active_trade["tp2"] else "TP1 HIT ✅")
                    trades.append(active_trade)
                    active_trade = None
                elif cur["low"] <= active_trade["sl"]:
                    active_trade["outcome"] = "WIN" if active_trade["sl"] >= active_trade["entry"] else "LOSS"
                    active_trade["status"] = "COST SHIELD 🛡️" if active_trade["sl"] >= active_trade["entry"] else "SL HIT ❌"
                    trades.append(active_trade)
                    active_trade = None
            else:
                if cur["low"] <= active_trade["entry"] - r_pts * 0.6:
                    active_trade["sl"] = min(active_trade["sl"], active_trade["entry"])
                if cur["low"] <= active_trade["tp1"]:
                    active_trade["outcome"] = "WIN"
                    active_trade["status"] = "TP3 MAX 🔥" if cur["low"] <= active_trade["tp3"] else ("TP2 HIT 🎯" if cur["low"] <= active_trade["tp2"] else "TP1 HIT ✅")
                    trades.append(active_trade)
                    active_trade = None
                elif cur["high"] >= active_trade["sl"]:
                    active_trade["outcome"] = "WIN" if active_trade["sl"] <= active_trade["entry"] else "LOSS"
                    active_trade["status"] = "COST SHIELD 🛡️" if active_trade["sl"] <= active_trade["entry"] else "SL HIT ❌"
                    trades.append(active_trade)
                    active_trade = None
            continue

        win_slice = rows[idx - 30: idx + 1]
        trs = [max(win_slice[j]["high"] - win_slice[j]["low"], abs(win_slice[j]["high"] - win_slice[j - 1]["close"]), abs(win_slice[j]["low"] - win_slice[j - 1]["close"])) for j in range(1, len(win_slice))]
        atr = sum(trs[-14:]) / 14.0
        if atr <= 0:
            continue

        cur_day = datetime.fromtimestamp(cur["time"]).strftime("%Y-%m-%d")
        cum_pv, cum_v = 0.0, 0.0
        for r in win_slice:
            if datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") == cur_day:
                tp = (r["high"] + r["low"] + r["close"]) / 3.0
                v = r["volume"] if r["volume"] > 0 else 1.0
                cum_pv += tp * v
                cum_v += v
        vwap_val = (cum_pv / cum_v) if cum_v > 0 else cur["close"]

        fabio = compute_fabio_orderflow_profile(win_slice, atr, dec)
        smc = compute_smc_features(win_slice, atr, dec)
        oc = build_option_chain_profile(sym, meta, win_slice, atr, dec, is_backtest=True)
        setup = evaluate_unified_confluence(fabio, smc, oc, win_slice, vwap_val, atr, dec)

        if setup["dir"] in ("BUY", "SELL"):
            dt_obj = datetime.fromtimestamp(cur["time"])
            active_trade = {
                "ts": cur["time"], "date": dt_obj.strftime("%Y-%m-%d"), "week": dt_obj.strftime("%Y-W%W"), "month": dt_obj.strftime("%Y-%m"),
                "time": dt_obj.strftime("%d %b %H:%M"), "clock_time": dt_obj.strftime("%H:%M"),
                "symbol": sym, "dir": setup["dir"], "strength": setup["strength"],
                "signal": setup["signal"], "reason": setup["reason"], "analysis": setup["analysis"],
                "entry": setup["entry"], "orig_sl": setup["sl"], "sl": setup["sl"],
                "tp1": setup["tp1"], "tp2": setup["tp2"], "tp3": setup["tp3"], "outcome": "OPEN", "status": "ACTIVE 🔒",
            }
    if active_trade:
        trades.append(active_trade)
    return trades


def build_historical_store():
    global HISTORICAL_TRADES
    all_trades = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for f in [pool.submit(run_backtest_for_symbol, s, ASSETS[s]) for s in FAVORITE_SYMBOLS if s in ASSETS]:
            try:
                all_trades.extend(f.result(timeout=16))
            except Exception:
                pass
    all_trades.sort(key=lambda x: x["ts"], reverse=True)
    HISTORICAL_TRADES = all_trades


def ensure_symbol_backtest(sym):
    if sym not in ASSETS or any(t["symbol"] == sym for t in HISTORICAL_TRADES):
        return
    new_t = run_backtest_for_symbol(sym, ASSETS[sym])
    if new_t:
        HISTORICAL_TRADES.extend(new_t)


def compute_win_ratio_stats():
    all_syms = FAVORITE_SYMBOLS + [s for s in list(ASSETS.keys()) if s not in FAVORITE_SYMBOLS]
    all_trades_out = []
    for x in sorted(HISTORICAL_TRADES, key=lambda item: item["ts"], reverse=True):
        all_trades_out.append({
            "ts": x["ts"], "date": x["date"], "week": x["week"], "month": x["month"],
            "timing": x.get("clock_time") or (x["time"].split(" ")[-1] if " " in x["time"] else x["time"]),
            "symbol": x["symbol"], "dir": x["dir"], "strength": x.get("strength", 75),
            "entry": x["entry"], "sl": x["sl"], "tp1": x["tp1"],
            "outcome": x["outcome"], "status": x["status"], "analysis": x.get("analysis", ""),
        })
    return {
        "since": BACKTEST_START_DATE,
        "all_symbols": all_syms,
        "favorite_symbols": FAVORITE_SYMBOLS,
        "trades": all_trades_out,
    }


def get_watchlist_snapshot():
    ordered = FAVORITE_SYMBOLS + [s for s in list(ASSETS.keys()) if s not in FAVORITE_SYMBOLS]
    out = []
    for sym in ordered:
        meta = ASSETS[sym]
        dec = meta["dec"]
        is_fav = sym in FAVORITE_SYMBOLS
        d = DATA_STORE.get(f"{sym}_15m")
        if d and d.get("candles"):
            c_list = d["candles"]
            last_p = c_list[-1]["c"]
            ref_p = c_list[0]["o"]
            chg = round(last_p - ref_p, dec)
            chg_pct = round(((last_p - ref_p) / max(1e-9, ref_p)) * 100.0, 2)
            sig = d["plan"]["signal"]
            strength = d["plan"].get("strength", 0)
            regime = d["plan"].get("regime", "RANGING")
            v_state = d["fabio"]["value_state"]
            vol_num = d["fabio"].get("cur_vol", 0)
            vol_ratio = d["fabio"].get("vol_ratio", 1.0)
            pcr = d["option_chain"]["pcr"]
            entry = d["plan"]["entry"]
            sl = d["plan"]["sl"]
            tp1 = d["plan"]["tp1"]
            entry_time = d["plan"].get("entry_time", "--")
            analysis = d["plan"].get("analysis", "")
        else:
            last_p, chg, chg_pct, sig, strength, regime, v_state, vol_num, vol_ratio, pcr, entry, sl, tp1, entry_time, analysis = (
                0.0, 0.0, 0.0, "WAIT", 0, "--", "TAP TO LOAD", 0, 1.0, 1.0, "--", "--", "--", "--", "Tap asset to load live data"
            )
        out.append({
            "symbol": sym, "name": meta["name"], "cat": meta["cat"], "is_fav": is_fav,
            "dec": dec, "price": last_p, "chg": chg, "chg_pct": chg_pct,
            "signal": sig, "strength": strength, "regime": regime,
            "value_state": v_state, "vol_num": vol_num, "vol_ratio": vol_ratio,
            "pcr": pcr, "entry": entry, "sl": sl, "tp1": tp1,
            "entry_time": entry_time, "analysis": analysis,
        })
    return out


def add_custom_watchlist_asset(raw_ticker, custom_name="", custom_cat="CUSTOM"):
    clean_input = raw_ticker.strip().upper().replace(" ", "")
    if not clean_input:
        return None
    if clean_input in ASSETS:
        if clean_input not in FAVORITE_SYMBOLS:
            FAVORITE_SYMBOLS.append(clean_input)
        compute_analytics(clean_input, "15m")
        threading.Thread(target=ensure_symbol_backtest, args=(clean_input,), daemon=True).start()
        return clean_input
    if clean_input in SYMBOL_ALIASES:
        y_tick, disp_name, cat, step, dec, alt_tick = SYMBOL_ALIASES[clean_input]
        sym_key = clean_input
        is_bn = y_tick.endswith("USDT")
        ASSETS[sym_key] = {
            "cat": cat, "name": custom_name.strip() or disp_name,
            "src": "BINANCE" if is_bn else "YAHOO",
            "ticker": y_tick, "alt": alt_tick,
            "is_idx": y_tick.startswith("^"), "step": step, "dec": dec,
        }
        if sym_key not in FAVORITE_SYMBOLS:
            FAVORITE_SYMBOLS.append(sym_key)
        compute_analytics(sym_key, "15m")
        threading.Thread(target=ensure_symbol_backtest, args=(sym_key,), daemon=True).start()
        return sym_key

    sym_key = clean_input.replace("=X", "").replace("=F", "").replace(".NS", "").replace("^", "")[:14]
    is_binance = clean_input.endswith("USDT")
    src = "BINANCE" if is_binance else "INDIA"
    if not any(clean_input.endswith(x) for x in ("=X", "=F", ".NS", ".BO", "USDT")) and not clean_input.startswith("^"):
        yahoo_tick = clean_input + ".NS"
        cat = "INDIA_STK"
    else:
        yahoo_tick = clean_input
        cat = "CRYPTO" if is_binance else ("INDIA_IDX" if clean_input.startswith("^") else custom_cat)

    ASSETS[sym_key] = {
        "cat": cat, "name": custom_name.strip() or f"{sym_key} ({cat})",
        "src": src, "ticker": yahoo_tick, "alt": clean_input, "nse": sym_key, "oc_sym": sym_key,
        "is_idx": clean_input.startswith("^"), "step": 10, "dec": 2,
    }
    if sym_key not in FAVORITE_SYMBOLS:
        FAVORITE_SYMBOLS.append(sym_key)
    compute_analytics(sym_key, "15m")
    threading.Thread(target=ensure_symbol_backtest, args=(sym_key,), daemon=True).start()
    return sym_key


# ==============================================================================
# 8. LIVE ANALYTICS & INSTITUTIONAL BAR TELEMETRY
# ==============================================================================
def compute_analytics(symbol, interval="15m"):
    if symbol not in ASSETS:
        return None
    cache_key = f"{symbol}_{interval}"
    now = time.time()
    meta = ASSETS[symbol]
    try:
        rows = fetch_candles_for_asset(meta, interval)
        if len(rows) < 5:
            return DATA_STORE.get(cache_key)

        tick_info = fetch_ultra_fast_live_tick(symbol)
        if tick_info and tick_info.get("price"):
            lp = tick_info["price"]
            rows[-1]["close"] = lp
            rows[-1]["high"] = max(rows[-1]["high"], lp)
            rows[-1]["low"] = min(rows[-1]["low"], lp)
            if tick_info.get("vol"):
                rows[-1]["volume"] = tick_info["vol"]

        dec = meta["dec"]
        latest_day = datetime.fromtimestamp(rows[-1]["time"]).strftime("%Y-%m-%d")
        cum_pv, cum_vol, vwap_vals = 0.0, 0.0, []
        for r in rows:
            if interval in ("1m", "3m", "5m", "15m", "30m", "45m") and datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") != latest_day:
                cum_pv, cum_vol = 0.0, 0.0
            tp = (r["high"] + r["low"] + r["close"]) / 3.0
            v = r["volume"] if r["volume"] > 0 else 1.0
            cum_pv += tp * v
            cum_vol += v
            vwap_vals.append(round(cum_pv / cum_vol, dec))
        vwap_val = vwap_vals[-1]

        trs = [max(rows[i]["high"] - rows[i]["low"], abs(rows[i]["high"] - rows[i - 1]["close"]), abs(rows[i]["low"] - rows[i - 1]["close"])) for i in range(1, len(rows))]
        atr = sum(trs[-14:]) / min(14, len(trs))
        last_close = rows[-1]["close"]

        fabio = compute_fabio_orderflow_profile(rows, atr, dec)
        smc = compute_smc_features(rows, atr, dec)
        oc = build_option_chain_profile(symbol, meta, rows, atr, dec, is_backtest=False)
        setup = evaluate_unified_confluence(fabio, smc, oc, rows, vwap_val, atr, dec)

        lock_key = f"{symbol}_{interval}"
        if lock_key in SIGNAL_LOCK:
            plan = SIGNAL_LOCK[lock_key]["plan"]
        elif setup["dir"] in ("BUY", "SELL"):
            trig_t = datetime.now().strftime("%d %b %H:%M:%S")
            plan = {
                "signal": setup["signal"], "strength": setup["strength"], "regime": setup["regime"],
                "vol_ratio": setup["vol_ratio"], "delta_pct": setup["delta_pct"],
                "reason": setup["reason"], "analysis": setup["analysis"],
                "entry_time": trig_t,
                "setup": f"{setup['signal']} | {setup['reason']} @ {trig_t} 🔒",
                "entry": setup["entry"], "sl": setup["sl"], "tp1": setup["tp1"], "tp2": setup["tp2"], "tp3": setup["tp3"],
                "buy_trigger": setup["buy_trigger"], "sell_trigger": setup["sell_trigger"], "locked": True,
            }
            SIGNAL_LOCK[lock_key] = {"ts": now, "plan": plan}
            send_telegram_signal(symbol, interval, plan)
        else:
            plan = {
                "signal": "WAIT", "strength": setup["strength"], "regime": setup["regime"],
                "vol_ratio": setup["vol_ratio"], "delta_pct": setup["delta_pct"],
                "reason": fabio["value_state"], "analysis": setup["analysis"],
                "entry_time": "--",
                "setup": f"[{setup['regime']}] Str:{setup['strength']}% | BUY > {setup['buy_trigger']} | SELL < {setup['sell_trigger']}",
                "entry": "--", "sl": "--", "tp1": "--", "tp2": "--", "tp3": "--",
                "buy_trigger": setup["buy_trigger"], "sell_trigger": setup["sell_trigger"], "locked": False,
            }

        eff_vols = [(r["volume"] if r["volume"] > 105.0 else (max(r["high"] - r["low"], 1e-9) * 1000.0)) for r in rows]
        avg_v_all = sum(eff_vols) / max(1, len(eff_vols))
        cvd_acc = 0.0
        candles = []
        for idx, r in enumerate(rows):
            rng = max(r["high"] - r["low"], 1e-9)
            body = abs(r["close"] - r["open"])
            ev = eff_vols[idx]
            buy_p = (r["close"] - r["low"]) / rng
            sell_p = (r["high"] - r["close"]) / rng
            delta = ev * (buy_p - sell_p)
            cvd_acc += delta
            vol_ratio = ev / max(1e-9, avg_v_all)
            is_abs = (vol_ratio >= 1.55) and (body <= rng * 0.35)
            bubble_size = round(vol_ratio, 2) if vol_ratio >= 1.45 else 0.0
            candles.append({
                "t": r["time"], "o": round(r["open"], dec), "h": round(r["high"], dec),
                "l": round(r["low"], dec), "c": round(r["close"], dec),
                "v": round(r["volume"], 1), "eff_v": round(ev, 1),
                "vwap": vwap_vals[idx], "delta": round(delta, 1), "cvd": round(cvd_acc, 1),
                "vol_ratio": round(vol_ratio, 2), "bubble": bubble_size, "absorb": is_abs,
            })

        res = {
            "symbol": symbol, "name": meta["name"], "cat": meta["cat"],
            "is_fav": (symbol in FAVORITE_SYMBOLS), "dec": dec,
            "price": round(last_close, dec), "vwap": round(vwap_val, dec),
            "fabio": fabio, "smc": smc, "option_chain": oc, "plan": plan,
            "candles": candles, "status": "LIVE"
        }
        DATA_STORE[cache_key] = res
        return res
    except Exception:
        return DATA_STORE.get(cache_key)


def background_refresh_loop():
    init_sessions()
    threading.Thread(target=build_historical_store, daemon=True).start()
    with ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            scan_syms = [s for s in FAVORITE_SYMBOLS if s in ASSETS]
            for f in [pool.submit(compute_analytics, s, "15m") for s in scan_syms]:
                try:
                    f.result(timeout=6)
                except Exception:
                    pass
            time.sleep(6)


# ==============================================================================
# 9. COMPLETE PRO WORKSPACE (ORIGINAL DESIGN PRESERVED + ALL 11 UPGRADES)
# ==============================================================================
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Pro TradingView & Option Desk — Live NSE + XM Spot + Volume Strength</title>
<style>
  :root {
    --tv-bg:#131722; --tv-panel:#1e222d; --tv-border:#2a2e39; --tv-text:#d1d4dc;
    --tv-muted:#787b86; --tv-blue:#2962ff; --tv-green:#089981; --tv-red:#f23645; --tv-gold:#facc15;
  }
  * { box-sizing:border-box; margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,"Trebuchet MS",Roboto,sans-serif; }
  html, body { width:100vw; max-width:100vw; height:100dvh; overflow:hidden; background:var(--tv-bg); color:var(--tv-text); display:flex; flex-direction:column; user-select:none; }

  .tv-top { min-height:40px; background:var(--tv-panel); border-bottom:1px solid var(--tv-border); display:flex; align-items:center; justify-content:space-between; padding:3px 6px; gap:4px; flex-shrink:0; overflow-x:auto; scrollbar-width:none; }
  .tv-top::-webkit-scrollbar { display:none; }
  .tv-top-left, .tv-top-right { display:flex; align-items:center; gap:3px; flex-shrink:0; }
  .tv-grp { display:flex; align-items:center; gap:2px; border-right:1px solid var(--tv-border); padding-right:5px; height:26px; flex-shrink:0; }
  .tv-grp:last-child { border-right:none; padding-right:0; }

  .sym-pill { background:#2962ff; color:#ffffff; border:1px solid #1e53e5; padding:4px 8px; border-radius:4px; font-size:11.5px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:4px; }
  .tv-btn { background:transparent; color:var(--tv-text); border:1px solid transparent; padding:4px 6px; border-radius:4px; font-size:10.5px; font-weight:700; cursor:pointer; white-space:nowrap; display:inline-flex; align-items:center; gap:3px; }
  .tv-btn:hover { background:rgba(41,98,255,0.14); }
  .tv-btn.active { color:#ffffff; background:#2962ff; font-weight:800; border-color:#2962ff; }

  .btn-dhan { background:#f59e0b; color:#111827 !important; border:1px solid #d97706; font-weight:800; }
  .btn-dhan.active { background:#d97706; color:#ffffff !important; }
  .btn-grid { background:#334155; color:#f8fafc !important; border:1px solid #475569; font-weight:800; }
  .btn-grid.active { background:#2962ff; color:#ffffff !important; }
  .btn-oc { background:#1d4ed8; color:#ffffff !important; border:1px solid #1e40af; font-weight:800; }
  .btn-wr { background:#047857; color:#ffffff !important; border:1px solid #065f46; font-weight:800; }
  .btn-sig { background:#7c3aed; color:#ffffff !important; border:1px solid #6d28d9; font-weight:800; }
  .btn-dict { background:#0f766e; color:#ffffff !important; border:1px solid #115e59; font-weight:800; }

  .tv-main { flex:1; width:100%; display:flex; min-height:0; overflow:hidden; position:relative; }

  .tv-leftbar { width:38px; background:var(--tv-panel); border-right:1px solid var(--tv-border); display:flex; flex-direction:column; align-items:center; padding:5px 0; gap:3px; flex-shrink:0; z-index:15; overflow-y:auto; scrollbar-width:none; }
  .tv-leftbar::-webkit-scrollbar { display:none; }
  .tool-btn { width:28px; height:28px; border-radius:5px; border:none; background:transparent; color:var(--tv-muted); font-size:14px; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .tool-btn:hover { background:rgba(41,98,255,0.16); color:var(--tv-text); }
  .tool-btn.active { background:#2962ff; color:#ffffff; }
  .tool-sep { width:20px; height:1px; background:var(--tv-border); margin:2px 0; flex-shrink:0; }

  .replay-bar { position:fixed; bottom:38px; left:50%; transform:translateX(-50%); background:#1e222d; border:1px solid #2962ff; border-radius:8px; padding:6px 10px; display:none; align-items:center; gap:6px; z-index:140; box-shadow:0 8px 24px rgba(0,0,0,0.75); color:#fff; font-size:11px; max-width:95vw; }
  .replay-bar.open { display:flex; }

  .draw-props { position:fixed; top:76px; left:42px; background:var(--tv-panel); border:1px solid var(--tv-border); border-radius:6px; padding:5px 9px; display:none; align-items:center; gap:6px; z-index:130; box-shadow:0 4px 14px rgba(0,0,0,0.6); font-size:11px; max-width:calc(100vw - 50px); flex-wrap:wrap; }
  .draw-props.open { display:flex; }
  .c-swatch { width:16px; height:16px; border-radius:50%; border:1.5px solid #fff; cursor:pointer; }

  .alert-toast { position:fixed; top:48px; right:16px; background:#1e222d; border:2px solid #facc15; color:#fff; padding:10px 14px; border-radius:8px; z-index:9999; display:none; font-size:12px; box-shadow:0 10px 30px rgba(0,0,0,0.85); max-width:320px; }
  .alert-toast.open { display:block; }

  .tv-center { flex:1; display:flex; flex-direction:column; min-width:0; min-height:0; position:relative; }
  .workspace-grid { flex:1; display:grid; min-height:0; gap:2px; background:var(--tv-border); overflow-y:auto; }
  .workspace-grid.mode-1 { grid-template-columns:1fr; grid-template-rows:1fr; }
  .workspace-grid.mode-3 { grid-template-columns:1.45fr 1fr; grid-template-rows:1fr 1fr; }
  .workspace-grid.mode-3 .pane-main { grid-row:1 / 3; }
  .workspace-grid.mode-4 { grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; }

  @media(max-width:850px) {
    .tv-top { flex-wrap:wrap; overflow-x:visible; padding:4px; gap:4px; }
    .tv-top-left, .tv-top-right { width:100%; overflow-x:auto; scrollbar-width:none; }
    .tv-top-left::-webkit-scrollbar, .tv-top-right::-webkit-scrollbar { display:none; }
    .tv-leftbar { width:32px; }
    .tool-btn { width:25px; height:25px; font-size:12.5px; }
    .tv-legend { right:62px; }
    .leg-line { gap:4px; font-size:10px; }
    .clean-stat { font-size:9.5px; }
    .tv-bot { height:auto; min-height:26px; flex-wrap:wrap; padding:3px 6px; gap:3px; }
    #bot-setup { width:100%; order:3; font-size:10px; }
    .workspace-grid.mode-3, .workspace-grid.mode-4 {
      grid-template-columns:1fr !important;
      grid-template-rows:none !important;
      grid-auto-rows:minmax(250px, 48vh);
    }
    .workspace-grid.mode-3 .pane-main { grid-row:auto !important; min-height:54vh; }
  }

  .pane { background:var(--tv-bg); position:relative; min-height:0; min-width:0; display:flex; flex-direction:column; overflow:hidden; }
  .pane-head { height:24px; background:var(--tv-panel); border-bottom:1px solid var(--tv-border); padding:0 8px; display:flex; align-items:center; justify-content:space-between; font-size:10.5px; font-weight:700; flex-shrink:0; }
  .pane-body { flex:1; position:relative; min-height:0; overflow:auto; }
  #fast-chart, #ce-chart, #pe-chart { width:100%; height:100%; display:block; touch-action:none; cursor:crosshair; }

  .tv-legend { position:absolute; top:6px; left:8px; right:68px; pointer-events:none; display:flex; flex-direction:column; gap:3px; z-index:10; }
  .leg-line { display:flex; flex-wrap:wrap; align-items:center; gap:7px; font-size:11.5px; }
  .bs-box { display:inline-flex; align-items:center; gap:4px; pointer-events:auto; }
  .sell-tag { border:1px solid #f23645; background:rgba(242,54,69,0.14); color:#f23645; padding:1px 5px; border-radius:4px; font-size:10px; font-weight:800; }
  .buy-tag { border:1px solid #2962ff; background:rgba(41,98,255,0.14); color:#2962ff; padding:1px 5px; border-radius:4px; font-size:10px; font-weight:800; }
  .clean-stat { font-size:11px; font-weight:800; letter-spacing:0.2px; }

  .tv-bot { height:28px; background:var(--tv-panel); border-top:1px solid var(--tv-border); display:flex; align-items:center; justify-content:space-between; padding:0 8px; font-size:11px; flex-shrink:0; gap:6px; overflow-x:auto; scrollbar-width:none; }
  .tv-bot::-webkit-scrollbar { display:none; }
  .rng-btn { background:transparent; border:none; color:var(--tv-muted); font-size:10.5px; font-weight:700; padding:2px 5px; border-radius:3px; cursor:pointer; }
  .rng-btn:hover, .rng-btn.active { color:#fff; background:#2962ff; }

  .tv-right { width:265px; background:var(--tv-panel); border-left:1px solid var(--tv-border); display:flex; flex-direction:column; flex-shrink:0; z-index:20; transition:width 0.15s; }
  .tv-right.collapsed { width:0; border-left:none; overflow:hidden; }
  @media(max-width:850px) {
    .tv-right { position:absolute; right:0; top:0; bottom:0; width:235px; max-width:85vw; box-shadow:-6px 0 18px rgba(0,0,0,0.65); }
    .tv-right.collapsed { width:0; }
  }
  .wl-head { height:32px; border-bottom:1px solid var(--tv-border); padding:0 8px; display:flex; align-items:center; justify-content:space-between; font-size:11px; font-weight:800; }
  .wl-search-wrap { padding:4px 6px; border-bottom:1px solid var(--tv-border); display:flex; flex-direction:column; gap:4px; }
  .wl-search { width:100%; background:#131722; border:1px solid #363a45; color:#fff; padding:4px 7px; border-radius:4px; font-size:11px; outline:none; }
  .wl-mode-tabs { display:flex; gap:3px; }
  .wl-tab { flex:1; text-align:center; background:#131722; color:#9ca3af; border:1px solid #2a2e39; border-radius:3px; padding:3px 4px; font-size:9.5px; font-weight:800; cursor:pointer; }
  .wl-tab.active { background:#2962ff; color:#fff; border-color:#2962ff; }
  .wl-cols { display:grid; grid-template-columns:1.35fr 0.9fr 0.75fr 0.35fr; padding:4px 8px; font-size:10px; color:var(--tv-muted); border-bottom:1px solid var(--tv-border); }
  .wl-list { flex:1; overflow-y:auto; }
  .wl-sec { padding:4px 8px; font-size:9.5px; font-weight:800; color:var(--tv-muted); background:rgba(0,0,0,0.15); letter-spacing:0.5px; }
  .wl-row { display:grid; grid-template-columns:1.35fr 0.9fr 0.75fr 0.35fr; padding:6px 8px; font-size:11px; border-bottom:1px solid rgba(120,123,134,0.2); cursor:pointer; align-items:center; }
  .wl-row:hover { background:rgba(41,98,255,0.12); }
  .wl-row.active { background:rgba(41,98,255,0.22); border-left:3px solid #2962ff; }
  .wl-del-btn { background:transparent; border:none; color:#9ca3af; font-size:12px; cursor:pointer; padding:2px; text-align:right; }
  .wl-del-btn:hover { color:#f23645; }
  .wl-detail { height:122px; border-top:1px solid var(--tv-border); background:rgba(0,0,0,0.12); padding:8px; display:flex; flex-direction:column; justify-content:space-between; font-size:11px; flex-shrink:0; }

  .pos { color:#089981; font-weight:800; } .neg { color:#f23645; font-weight:800; } .gold { color:#d97706; font-weight:800; } .purp { color:#9333ea; font-weight:800; } .cyan { color:#0284c7; font-weight:800; }

  .tv-drawer { position:absolute; inset:0; background:var(--tv-bg); z-index:45; display:none; flex-direction:column; overflow:hidden; }
  .tv-drawer.open { display:flex; }
  .drawer-head { background:var(--tv-panel); border-bottom:1px solid var(--tv-border); padding:6px 8px; display:flex; justify-content:space-between; align-items:center; gap:4px; flex-wrap:wrap; }
  .drawer-body { flex:1; overflow-y:auto; padding:8px; }
  .card { background:var(--tv-panel); border:1px solid var(--tv-border); border-radius:8px; padding:8px; margin-bottom:10px; }
  .card-title { font-size:11px; color:var(--tv-muted); text-transform:uppercase; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; font-weight:700; gap:6px; flex-wrap:wrap; }
  .wr-summary-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; margin-bottom:10px; }
  @media(max-width:700px) { .wr-summary-grid { grid-template-columns:repeat(2, 1fr); } }
  .wr-kpi { background:rgba(120,123,134,0.08); border:1px solid var(--tv-border); border-radius:8px; padding:7px; }
  .wr-kpi-label { font-size:9.5px; color:var(--tv-muted); text-transform:uppercase; font-weight:700; }
  .wr-kpi-val { font-size:16px; font-weight:800; margin:2px 0; }

  .tbl-scroll { width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; }
  table { width:100%; border-collapse:collapse; font-size:11px; }
  th, td { padding:6px 5px; text-align:center; border-bottom:1px solid var(--tv-border); white-space:nowrap; }
  th { color:var(--tv-muted); font-size:9.5px; text-transform:uppercase; background:rgba(120,123,134,0.12); font-weight:800; }
  .atm-row { background:rgba(250,204,21,0.18) !important; }
  .sticky-strike { position:sticky; left:0; right:0; z-index:5; background:#2a2e39 !important; color:#facc15 !important; font-weight:800; }

  .wr-black-card { background:#f8fafc !important; color:#000000 !important; border:2px solid #000000 !important; }
  .wr-black-card .card-title { color:#000000 !important; font-weight:900; }
  .wr-black-tbl th { background:#cbd5e1 !important; color:#000000 !important; font-weight:900; border-bottom:1.5px solid #000000; }
  .wr-black-tbl td { color:#000000 !important; font-weight:800; border-bottom:1px solid #94a3b8; }
  .wr-black-tbl tr:hover { background:#e2e8f0; }
  .trade-pill-list { display:flex; flex-wrap:wrap; gap:5px; justify-content:flex-start; text-align:left; white-space:normal; min-width:240px; max-width:560px; }
  .trade-pill { display:inline-flex; align-items:center; gap:4px; background:#ffffff; border:1.5px solid #000000; color:#000000 !important; font-weight:900; font-size:10.5px; padding:3px 7px; border-radius:4px; cursor:pointer; }
  .trade-pill:hover { background:#dbeafe; }

  .dict-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:8px; }
  .dict-item { background:#131722; border:1px solid #2a2e39; border-radius:6px; padding:8px; }
  .dict-term { font-size:12px; font-weight:800; color:#facc15; margin-bottom:3px; }
  .dict-desc { font-size:11px; color:#d1d4dc; line-height:1.4; }
  .dict-imp { font-size:10.5px; color:#38bdf8; margin-top:4px; font-weight:700; }

  .ltp-btn { background:#1e40af; color:#ffffff !important; border:1px solid #1d4ed8; padding:3px 7px; border-radius:4px; font-size:10.5px; cursor:pointer; font-weight:800; }
  .ltp-btn:hover { background:#2563eb; }
  .sub-view { display:none; } .sub-view.active { display:block; }

  .modal-bg { position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:9999; display:none; align-items:center; justify-content:center; padding:8px; }
  .modal-bg.open { display:flex; }
  .modal-box { background:#1e222d; border:1px solid #363a45; border-radius:10px; padding:12px; max-width:540px; width:100%; box-shadow:0 12px 32px rgba(0,0,0,0.85); color:#d1d4dc; max-height:90dvh; overflow-y:auto; }
  .inp-dark { width:100%; background:#131722; border:1px solid #363a45; color:#fff; padding:7px 9px; border-radius:5px; font-size:12px; margin:5px 0 10px 0; }
  .link-row { background:#131722; border:1px solid #363a45; border-radius:6px; padding:8px 10px; margin:8px 0; display:flex; justify-content:space-between; align-items:center; gap:8px; }

  .ctx-menu { position:fixed; background:#1e222d; border:1px solid #363a45; border-radius:6px; padding:5px 0; width:235px; z-index:9998; display:none; flex-direction:column; box-shadow:0 10px 28px rgba(0,0,0,0.8); font-size:12px; }
  .ctx-menu.open { display:flex; }
  .ctx-item { padding:7px 14px; color:#d1d4dc; cursor:pointer; display:flex; align-items:center; justify-content:space-between; }
  .ctx-item:hover { background:#2a2e39; color:#fff; }
  .ctx-sep { height:1px; background:#2a2e39; margin:4px 0; }

  .tv-set-modal { width:560px; max-width:96vw; height:430px; max-height:86vh; background:#1e222d; border:1px solid #363a45; border-radius:8px; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 16px 40px rgba(0,0,0,0.9); }
  .tv-set-head { height:42px; padding:0 14px; border-bottom:1px solid #2a2e39; display:flex; align-items:center; justify-content:space-between; font-size:15px; font-weight:700; color:#fff; }
  .tv-set-body { flex:1; display:flex; min-height:0; }
  .tv-set-nav { width:125px; border-right:1px solid #2a2e39; padding:8px 5px; display:flex; flex-direction:column; gap:3px; background:#181c27; overflow-y:auto; }
  .set-nav-btn { text-align:left; background:transparent; border:none; color:#d1d4dc; padding:8px 8px; border-radius:5px; font-size:11.5px; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:6px; }
  .set-nav-btn:hover { background:#2a2e39; }
  .set-nav-btn.active { background:#2a2e39; color:#fff; font-weight:700; }
  .tv-set-content { flex:1; padding:12px 14px; overflow-y:auto; display:flex; flex-direction:column; gap:11px; font-size:12px; }
  .set-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
  .set-chk { display:flex; align-items:center; gap:8px; cursor:pointer; color:#d1d4dc; font-size:12px; }
  .set-chk input { width:15px; height:15px; accent-color:#2962ff; }
  .tv-set-foot { height:46px; padding:0 14px; border-top:1px solid #2a2e39; display:flex; align-items:center; justify-content:space-between; background:#181c27; }
</style>
</head>
<body>

<div class="alert-toast" id="alert-toast"></div>

<div class="tv-top">
  <div class="tv-top-left">
    <div class="tv-grp">
      <button class="sym-pill" onclick="toggleWatchlist()" title="Switch Symbol">🔍 <span id="top-sym">XAUUSD</span></button>
    </div>
    <div class="tv-grp" id="tf-group">
      <button class="tv-btn" onclick="setTF('1m', this)">1m</button>
      <button class="tv-btn" onclick="setTF('3m', this)">3m</button>
      <button class="tv-btn" onclick="setTF('5m', this)">5m</button>
      <button class="tv-btn active" onclick="setTF('15m', this)">15m</button>
      <button class="tv-btn" onclick="setTF('30m', this)">30m</button>
      <button class="tv-btn" onclick="setTF('45m', this)">45m</button>
      <button class="tv-btn" onclick="setTF('1h', this)">1h</button>
      <button class="tv-btn" onclick="setTF('2h', this)">2h</button>
      <button class="tv-btn" onclick="setTF('3h', this)">3h</button>
      <button class="tv-btn" onclick="setTF('4h', this)">4h</button>
      <button class="tv-btn" onclick="setTF('1d', this)">1D</button>
      <button class="tv-btn" onclick="setTF('1w', this)">1W</button>
      <button class="tv-btn" onclick="setTF('1M', this)">1M</button>
    </div>
    <div class="tv-grp">
      <button class="tv-btn" onclick="openModal('ind-modal', event)">📊 Indicators</button>
      <button class="tv-btn" onclick="openModal('theme-modal', event)">🎨 Theme</button>
      <button class="tv-btn" onclick="openModal('alert-modal', event)">⏰ Alerts (<span id="alert-cnt">0</span>)</button>
      <button class="tv-btn" id="replay-btn" onclick="toggleReplay()">⏪ Replay</button>
    </div>
  </div>

  <div class="tv-top-right">
    <button class="tv-btn" id="refresh-btn" onclick="forceRefreshChart()" title="Refresh Live Data Now">🔄 Refresh</button>
    <button class="tv-btn btn-dict" onclick="openModal('dict-modal', event)" title="Chart Labels & Signal Analysis Dictionary">📖 Dictionary</button>
    <button class="tv-btn btn-dhan" id="dhan-btn" onclick="setWorkspaceLayout(layoutMode===3 ? 1 : 3)" title="3-Window Option Desk">🇮🇳 3-Chart</button>
    <button class="tv-btn btn-grid" id="grid4-btn" onclick="setWorkspaceLayout(layoutMode===4 ? 1 : 4)" title="4-Window Split Screen">⊞ 4-Grid</button>
    <button class="tv-btn btn-sig" onclick="openDrawer('allsignals')" title="Favorite Assets Live Signal Matrix">📡 Signals</button>
    <button class="tv-btn btn-oc" onclick="openDrawer('optionchain')">⛓ Option Chain</button>
    <button class="tv-btn btn-wr" onclick="openDrawer('winratio')">🏆 Win (<span id="wr-badge">--%</span>)</button>
    <button class="tv-btn" onclick="openSettingsModal()" title="Chart Settings">⚙️</button>
    <button class="tv-btn" onclick="openPcModal()" title="PC Share Link">💻</button>
    <button class="tv-btn" onclick="unlockCurrent()" title="Unlock Setup">🔓</button>
    <button class="tv-btn" onclick="saveChartPng()" title="Screenshot">📷</button>
    <button class="tv-btn active" id="wl-toggle-btn" onclick="toggleWatchlist()" title="Watchlist">📋</button>
  </div>
</div>

<div class="replay-bar" id="replay-bar">
  <b style="color:#38bdf8;">⏪ REPLAY</b>
  <span style="font-size:10px;color:#9ca3af;" id="replay-status">Tap bar to cut</span>
  <button class="tv-btn active" id="rep-play-btn" onclick="toggleReplayPlay()">▶ Play</button>
  <button class="tv-btn" onclick="stepReplay(1)">⏭ Step</button>
  <select id="rep-speed" style="background:#131722;color:#fff;border:1px solid #363a45;border-radius:4px;padding:2px 4px;font-size:10.5px;">
    <option value="1000">1x</option>
    <option value="500" selected>2x</option>
    <option value="200">5x</option>
  </select>
  <button class="tv-btn" style="color:#f23645;" onclick="toggleReplay()">✕</button>
</div>

<div class="draw-props" id="draw-props">
  <span style="color:#787b86;font-weight:700;">Color:</span>
  <div class="c-swatch" style="background:#facc15;" onclick="updateSelectedDrawColor('#facc15')"></div>
  <div class="c-swatch" style="background:#38bdf8;" onclick="updateSelectedDrawColor('#38bdf8')"></div>
  <div class="c-swatch" style="background:#089981;" onclick="updateSelectedDrawColor('#089981')"></div>
  <div class="c-swatch" style="background:#f23645;" onclick="updateSelectedDrawColor('#f23645')"></div>
  <div class="c-swatch" style="background:#ffffff;" onclick="updateSelectedDrawColor('#ffffff')"></div>
  <button class="tv-btn" style="color:#f23645;font-weight:800;" onclick="deleteSelectedDrawing()">🗑 Delete</button>
  <button class="tv-btn" onclick="selectedDrawIdx=-1; document.getElementById('draw-props').classList.remove('open'); renderAllCharts();">✕</button>
</div>

<div class="tv-main">
  <div class="tv-leftbar">
    <button class="tool-btn active" id="tool-cursor" onclick="setDrawTool('cursor')" title="Crosshair / Select & Resize">✛</button>
    <button class="tool-btn" id="tool-alert" onclick="setDrawTool('alert')" title="Add Price Alert Line">⏰</button>
    <button class="tool-btn" id="tool-hline" onclick="setDrawTool('hline')" title="Horizontal Line">―</button>
    <button class="tool-btn" id="tool-ray" onclick="setDrawTool('ray')" title="Horizontal Ray">➔</button>
    <button class="tool-btn" id="tool-trend" onclick="setDrawTool('trend')" title="Trendline">╱</button>
    <button class="tool-btn" id="tool-box" onclick="setDrawTool('box')" title="Zone Rectangle">▭</button>
    <button class="tool-btn" id="tool-fib" onclick="setDrawTool('fib')" title="Fib Retracement">☰</button>
    <button class="tool-btn" id="tool-long" onclick="setDrawTool('long')" title="Long RR Position">📈</button>
    <button class="tool-btn" id="tool-short" onclick="setDrawTool('short')" title="Short RR Position">📉</button>
    <button class="tool-btn" id="tool-text" onclick="setDrawTool('text')" title="Text Note">T</button>
    <div class="tool-sep"></div>
    <button class="tool-btn" id="tool-measure" onclick="setDrawTool('measure')" title="Ruler">📏</button>
    <button class="tool-btn" onclick="zoomChart(-12)" title="Zoom In">🔍</button>
    <button class="tool-btn" onclick="resetView()" title="Reset Zoom/Pan">⟲</button>
    <div class="tool-sep"></div>
    <button class="tool-btn active" id="btn-hide-draw" onclick="toggleDrawingsVisibility()" title="Hide / Show All Drawings">👁</button>
    <button class="tool-btn" onclick="undoDrawing()" title="Undo Drawing">↩</button>
    <button class="tool-btn" onclick="clearDrawings()" title="Remove All Drawings">🗑</button>
  </div>

  <div class="tv-center">
    <div class="workspace-grid mode-1" id="workspace-grid">
      <div class="pane pane-main" id="pane-1">
        <div class="tv-legend">
          <div class="leg-line" id="leg1">Loading...</div>
          <div class="leg-line" id="leg2"></div>
          <div class="leg-line" id="leg3"></div>
        </div>
        <canvas id="fast-chart"></canvas>
      </div>

      <div class="pane" id="pane-2" style="display:none;">
        <div class="pane-head">
          <span class="pos" id="ce-pane-title">📈 CALL (CE) LTP CHART</span>
          <select id="ce-strike-sel" onchange="syncSelectedStrikes()" style="background:#131722;color:#facc15;border:1px solid #363a45;border-radius:3px;font-size:10px;padding:1px 4px;"></select>
        </div>
        <div class="pane-body"><canvas id="ce-chart"></canvas></div>
      </div>

      <div class="pane" id="pane-3" style="display:none;">
        <div class="pane-head">
          <span class="neg" id="pe-pane-title">📉 PUT (PE) LTP CHART</span>
          <select id="pe-strike-sel" onchange="syncSelectedStrikes()" style="background:#131722;color:#facc15;border:1px solid #363a45;border-radius:3px;font-size:10px;padding:1px 4px;"></select>
        </div>
        <div class="pane-body"><canvas id="pe-chart"></canvas></div>
      </div>

      <div class="pane" id="pane-4" style="display:none;">
        <div class="pane-head">
          <span class="gold">📡 FAVORITE SIGNALS</span>
          <button class="tv-btn" style="padding:1px 4px;font-size:9.5px;" onclick="openDrawer('allsignals')">Expand ↗</button>
        </div>
        <div class="pane-body" id="mini-sig-body" style="padding:5px;font-size:10.5px;">Loading Signals...</div>
      </div>
    </div>

    <div class="tv-bot">
      <div style="display:flex;align-items:center;gap:2px;">
        <button class="rng-btn" onclick="setVisibleBars(30, this)">1D</button>
        <button class="rng-btn active" onclick="setVisibleBars(80, this)">5D</button>
        <button class="rng-btn" onclick="setVisibleBars(250, this)">1M</button>
        <button class="rng-btn" onclick="setVisibleBars(900, this)">2M (All)</button>
      </div>
      <div id="bot-setup" style="font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Scanning Favorite Watchlist...</div>
      <div id="ist-clock" style="font-weight:700;white-space:nowrap;">--:--:-- UTC+5:30</div>
    </div>

    <div class="tv-drawer" id="tv-drawer">
      <div class="drawer-head">
        <div style="display:flex;gap:4px;flex-wrap:wrap;">
          <button class="tv-btn" id="dtab-allsignals" onclick="switchDrawer('allsignals')">📡 Favorite Signals Matrix</button>
          <button class="tv-btn active" id="dtab-optionchain" onclick="switchDrawer('optionchain')">⛓ Option Chain</button>
          <button class="tv-btn" id="dtab-winratio" onclick="switchDrawer('winratio')">🏆 Win Ratio (2 Months)</button>
        </div>
        <button class="tv-btn" style="background:#f23645;color:#fff;" onclick="closeDrawer()">✕ Back to Chart</button>
      </div>
      <div class="drawer-body">
        <div id="sub-allsignals" class="sub-view">
          <div class="card">
            <div class="card-title">
              <span>📡 Live Favorite Watchlist Signal Matrix (With Entry Time & Logic Analysis)</span>
              <button class="tv-btn btn-dict" style="padding:2px 7px;font-size:10px;" onclick="openModal('dict-modal', event)">📖 Open Logic Dictionary</button>
            </div>
            <div class="tbl-scroll">
              <table>
                <thead><tr><th>Asset</th><th>Market Bias</th><th>Live Price</th><th>Vol (Ratio)</th><th>Strength</th><th>Signal</th><th>Entry Time</th><th>Entry</th><th>SL</th><th>TP1</th><th style="text-align:left;">Why Entry Signal Formed (Analysis)</th></tr></thead>
                <tbody id="all-sig-tbody"></tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="sub-optionchain" class="sub-view active">
          <div class="wr-summary-grid" id="oc-kpi"></div>
          <div class="card">
            <div class="card-title"><span id="oc-title">15-Strike Option Chain (Tap CE/PE LTP for Option Chart)</span></div>
            <div class="tbl-scroll">
              <table>
                <thead><tr><th>CE Buildup</th><th>CE OI</th><th>IV%</th><th>Δ</th><th>Γ</th><th>Θ</th><th>CE LTP</th><th class="sticky-strike">STRIKE</th><th>PE LTP</th><th>Δ</th><th>PE OI</th><th>PE Buildup</th></tr></thead>
                <tbody id="oc-tbody"></tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="sub-winratio" class="sub-view">
          <div class="card">
            <div class="card-title">
              <span>🎯 Select Assets for Win Accuracy Dashboard (2 Months History)</span>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">
                <button class="tv-btn active" style="padding:2px 7px;font-size:10px;" onclick="selectWRPreset('FAV')">⭐ My Favorites</button>
                <button class="tv-btn" style="padding:2px 7px;font-size:10px;border:1px solid #363a45;" onclick="selectWRPreset('ALL')">✅ Select All</button>
                <button class="tv-btn" style="padding:2px 7px;font-size:10px;border:1px solid #363a45;" onclick="selectWRPreset('NONE')">Clear</button>
              </div>
            </div>
            <div id="wr-asset-selector" style="display:flex;flex-wrap:wrap;gap:5px;max-height:125px;overflow-y:auto;padding-top:4px;"></div>
          </div>

          <div class="wr-summary-grid" id="wr-kpi"></div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:10px;margin-bottom:10px;">
            <div class="card" style="display:flex;flex-direction:column;align-items:center;justify-content:center;">
              <div class="card-title" style="width:100%;"><span>🎯 Win vs Loss Ratio (Selected)</span></div>
              <canvas id="wr-donut-canvas" width="180" height="150"></canvas>
            </div>
            <div class="card">
              <div class="card-title"><span>📊 Selected Assets Win Accuracy Bars</span></div>
              <div id="wr-visual-bars" style="display:flex;flex-direction:column;gap:8px;"></div>
            </div>
          </div>
          <div class="card">
            <div class="card-title"><span>⭐ Selected Assets Win Ratio Breakdown (Last 2 Months)</span></div>
            <div class="tbl-scroll">
              <table>
                <thead><tr><th>Asset</th><th>Total</th><th>Wins</th><th>Losses</th><th>Open</th><th>Win Ratio %</th></tr></thead>
                <tbody id="wr-focus-tbody"></tbody>
              </table>
            </div>
          </div>
          <div class="card wr-black-card">
            <div class="card-title">
              <span>DAILY / WEEKLY / MONTHLY BREAKDOWN [V2-BLACK-LOG]</span>
              <div style="display:flex;gap:4px;">
                <button class="tv-btn active" id="wrm-daily" onclick="wrMode='daily'; renderWRTables();">Daily</button>
                <button class="tv-btn" id="wrm-weekly" style="color:#000;" onclick="wrMode='weekly'; renderWRTables();">Weekly</button>
                <button class="tv-btn" id="wrm-monthly" style="color:#000;" onclick="wrMode='monthly'; renderWRTables();">Monthly</button>
              </div>
            </div>
            <div class="tbl-scroll">
              <table class="wr-black-tbl">
                <thead><tr><th>PERIOD</th><th>TOTAL</th><th>WINS</th><th>LOSSES</th><th>OPEN</th><th>WIN RATIO %</th><th style="text-align:left;">ASSET • BUY/SELL • ENTRY TIMING • RESULT</th></tr></thead>
                <tbody id="wr-period-tbody"><tr><td colspan="7" style="color:#000000;font-weight:900;">Loading Historical Trades...</td></tr></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="tv-right" id="tv-right">
    <div class="wl-head">
      <span>⭐ Favorite Watchlist</span>
      <div style="display:flex;gap:3px;">
        <button class="tv-btn active" onclick="openModal('add-sym-modal', event)" title="Add Symbol to Favorites" style="padding:2px 6px;font-size:13px;font-weight:900;">+</button>
        <button class="tv-btn" onclick="toggleWatchlist()" style="padding:2px 5px;">✕</button>
      </div>
    </div>
    <div class="wl-search-wrap">
      <div class="wl-mode-tabs">
        <button class="wl-tab active" id="wltab-fav" onclick="setWLMode('FAV')">⭐ My Favorites</button>
        <button class="wl-tab" id="wltab-all" onclick="setWLMode('ALL')">🌐 All Catalog</button>
      </div>
      <input type="text" id="wl-search-inp" class="wl-search" placeholder="🔍 Filter or search any symbol..." oninput="renderWatchlistDOM()">
    </div>
    <div class="wl-cols">
      <span>Symbol</span><span style="text-align:right;">Last</span><span style="text-align:right;">Chg%</span><span style="text-align:right;">Act</span>
    </div>
    <div class="wl-list" id="wl-list">Loading...</div>
    <div class="wl-detail" id="wl-detail">
      <div><b class="gold" id="wld-sym">XAUUSD</b> • <span id="wld-cat" style="color:#787b86;">COMMODITY</span></div>
      <div id="wld-name" style="font-weight:600;">Gold Spot (XM)</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <b id="wld-price" style="font-size:16px;">--</b>
        <span id="wld-state" class="cyan" style="font-size:10px;">--</span>
      </div>
      <div id="wld-pcr" style="font-size:10px;color:#787b86;">Vol: -- | PCR: --</div>
    </div>
  </div>
</div>

<!-- CHART LABELS & SIGNAL ANALYSIS DICTIONARY MODAL -->
<div class="modal-bg" id="dict-modal" onclick="if(event.target===this) closeModal('dict-modal')">
  <div class="modal-box" style="max-width:740px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <b style="color:#facc15;font-size:14px;">📖 Chart Labels & Live Signal Logic Dictionary</b>
      <button class="tv-btn" onclick="closeModal('dict-modal')">✕</button>
    </div>

    <div style="background:#131722;border:1px solid #2962ff;border-radius:6px;padding:8px 10px;margin-bottom:10px;">
      <div style="font-size:10.5px;color:#38bdf8;font-weight:800;margin-bottom:3px;">🔍 CURRENT CHART LIVE SIGNAL ANALYSIS (<span id="dict-cur-sym">XAUUSD</span>)</div>
      <div id="dict-live-analysis" style="font-size:11.5px;color:#ffffff;font-weight:700;">Loading current asset logic...</div>
    </div>

    <div class="dict-grid">
      <div class="dict-item">
        <div class="dict-term">POC (Point of Control)</div>
        <div class="dict-desc">वह प्राइस लेवल जहाँ पिछले 36 कैंडल्स में सबसे ज़्यादा वॉल्यूम ट्रेड हुआ है।</div>
        <div class="dict-imp">महत्व: यह इंस्टीट्यूशनल फेयर वैल्यू है; प्राइस बार-बार POC की तरफ़ खिंचता है या यहाँ से बड़ा बाउंस लेता है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">VAH & VAL (Value Area High / Low)</div>
        <div class="dict-desc">कुल वॉल्यूम का 70% हिस्सा जिस ऊपरी (VAH) और निचली (VAL) सीमा के बीच ट्रेड हुआ है।</div>
        <div class="dict-imp">महत्व: VAH के ऊपर सस्टेन करना Bullish Breakout और VAL के नीचे जाना Bearish Breakdown दिखाता है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">LVN (Low Volume Node)</div>
        <div class="dict-desc">वॉल्यूम प्रोफ़ाइल का वह पतला हिस्सा जहाँ बहुत कम ऑर्डर्स लगे होते हैं।</div>
        <div class="dict-imp">महत्व: यहाँ लिक्विडिटी कम होने के कारण प्राइस बहुत तेज़ी से (Rocket Move) आर-पार निकलता है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">THE CAGE (CHOP) ⚠️</div>
        <div class="dict-desc">जब प्राइस VAH और VAL के बीच फंसा होता है और कोई नई दिशा नहीं बनती।</div>
        <div class="dict-imp">महत्व: यह नो-ट्रेड ज़ोन (Sideways Trap) है; यहाँ ओवर-ट्रेडिंग से बचना चाहिए।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">CVD (Cumulative Volume Delta)</div>
        <div class="dict-desc">असली Buying Volume और Selling Volume का संचयी अंतर (नीचे वाला सब-पेन)।</div>
        <div class="dict-imp">महत्व: यदि प्राइस गिर रहा हो लेकिन CVD ऊपर जाए, तो बड़े बायर्स चुपचाप माल खरीद रहे हैं (Bullish Divergence)।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">BULL OB / BEAR OB (Order Blocks)</div>
        <div class="dict-desc">तेज़ इंस्टीट्यूशनल मूव से ठीक पहले की आखिरी विपरीत कैंडल (Smart Money Footprint)।</div>
        <div class="dict-imp">महत्व: रीटेस्ट पर यहाँ से हाई-एक्यूरेसी रिवर्सल और टाइट स्टॉप-लॉस मिलता है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">PDH / PDL / pPOC</div>
        <div class="dict-desc">पिछले दिन का High (PDH), Low (PDL) और पिछले दिन का Point of Control (pPOC)।</div>
        <div class="dict-imp">महत्व: रिटेल स्टॉप-लॉस इन्हीं लेवल्स के पास होते हैं; यहाँ Liquidity Sweep होने पर असली ट्रेड बनता है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">CALL WALL / PUT WALL & PCR</div>
        <div class="dict-desc">ऑप्शन चेन में सबसे ज़्यादा Call OI (रेजिस्टेंस) और Put OI (सपोर्ट) वाली स्ट्राइक।</div>
        <div class="dict-imp">महत्व: PCR ≥ 1.10 बुलिश और ≤ 0.90 बेयरिश सेंटीमेंट दिखाता है; Walls टारगेट बुक करने के लिए बेस्ट हैं।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">THIN BOOK BLAST / ABSORPTION</div>
        <div class="dict-desc">कम वॉल्यूम पर बड़ी कैंडल (Thin Book) या भारी वॉल्यूम पर छोटी कैंडल (Absorption)।</div>
        <div class="dict-imp">महत्व: Absorption का मतलब है कि बड़े प्लेयर्स ने आक्रामक बायर्स या सेलर्स को सोख लिया है और ट्रेंड पलटने वाला है।</div>
      </div>
      <div class="dict-item">
        <div class="dict-term">Signal Strength % & Regime Filter</div>
        <div class="dict-desc">वॉल्यूम स्पाइक (≥1.05x), ट्रेंड (EMA+VWAP), Delta और SMC के आधार पर 0–100% स्कोर।</div>
        <div class="dict-imp">महत्व: केवल ≥65% स्ट्रेंथ और ट्रेंड की दिशा में ही सिग्नल जनरेट होता है ताकि फेक सिग्नल रुक सकें।</div>
      </div>
    </div>
  </div>
</div>

<div class="ctx-menu" id="chart-ctx-menu">
  <div class="ctx-item" onclick="addPriceAlertAt(parseFloat(lastRightClickPrice)); closeCtxMenu();"><span>⏰ Add Alert at Price</span><b id="ctx-alert-val" class="gold">--</b></div>
  <div class="ctx-item" onclick="addHLineAt(parseFloat(lastRightClickPrice)); closeCtxMenu();"><span>― Add Horizontal Line</span></div>
  <div class="ctx-sep"></div>
  <div class="ctx-item" onclick="resetView(); closeCtxMenu();"><span>⟲ Reset Zoom & Y-Scale</span><span style="color:#787b86;font-size:10px;">Alt+R</span></div>
  <div class="ctx-item" onclick="copyCtxPrice(); closeCtxMenu();"><span>📋 Copy Price</span><b id="ctx-price-val" class="cyan">--</b></div>
  <div class="ctx-sep"></div>
  <div class="ctx-item" onclick="toggleDrawingsVisibility(); closeCtxMenu();"><span>👁 Hide / Show Drawings</span></div>
  <div class="ctx-item" onclick="clearDrawings(); closeCtxMenu();"><span>🗑 Remove All Drawings</span></div>
  <div class="ctx-sep"></div>
  <div class="ctx-item" onclick="openModal('ind-modal'); closeCtxMenu();"><span>📊 Indicators, CVD & Script...</span></div>
  <div class="ctx-item" onclick="openModal('theme-modal'); closeCtxMenu();"><span>🎨 Color Theme...</span></div>
  <div class="ctx-item" onclick="openSettingsModal(); closeCtxMenu();"><span>⚙️ Settings...</span></div>
</div>

<div class="modal-bg" id="alert-modal" onclick="if(event.target===this) closeModal('alert-modal')">
  <div class="modal-box" style="max-width:420px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <b style="color:#facc15;font-size:13.5px;">⏰ Custom Price Alerts (Sound + Telegram)</b>
      <button class="tv-btn" onclick="closeModal('alert-modal')">✕</button>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:10px;">
      <input type="number" step="any" id="new-alert-price" class="inp-dark" style="margin:0;flex:1;" placeholder="Target Price">
      <input type="text" id="new-alert-note" class="inp-dark" style="margin:0;flex:1;" placeholder="Note (Optional)">
      <button class="tv-btn active" onclick="submitNewAlert()">+ Add</button>
    </div>
    <div id="alert-list-body" style="display:flex;flex-direction:column;gap:5px;max-height:240px;overflow-y:auto;"></div>
  </div>
</div>

<div class="modal-bg" id="ind-modal" onclick="if(event.target===this) closeModal('ind-modal')">
  <div class="modal-box" style="max-width:450px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <b style="color:#facc15;font-size:13.5px;">📊 Indicators, CVD & My Script</b>
      <div style="display:flex;gap:4px;">
        <button class="tv-btn active" style="padding:2px 6px;font-size:10px;" onclick="toggleAllPlots()">👁 All On/Off</button>
        <button class="tv-btn" onclick="closeModal('ind-modal')">✕</button>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:7px;margin-bottom:10px;">
      <label class="set-chk" style="justify-content:space-between;"><span>Volume Profile + LVN</span><input type="checkbox" id="chk-vp" checked onchange="showVP=this.checked; savePrefs(); renderAllCharts();"></label>
      <div class="set-row" style="padding-left:12px;font-size:11px;color:#9ca3af;">
        <span>VP Bar Colors (POC / VA / Base):</span>
        <div>
          <input type="color" id="col-vp-poc" value="#facc15" onchange="vpPocColor=this.value; savePrefs(); renderAllCharts();">
          <input type="color" id="col-vp-va" value="#38bdf8" onchange="vpVaColor=this.value; savePrefs(); renderAllCharts();">
          <input type="color" id="col-vp-base" value="#787b86" onchange="vpBaseColor=this.value; savePrefs(); renderAllCharts();">
        </div>
      </div>
      <label class="set-chk" style="justify-content:space-between;"><span>CVD Delta Sub-Pane</span><input type="checkbox" id="chk-cvd" checked onchange="showCVD=this.checked; savePrefs(); renderAllCharts();"></label>
      <div class="set-row" style="padding-left:12px;font-size:11px;color:#9ca3af;">
        <span>CVD Colors (Line / +Bar / -Bar / BG):</span>
        <div>
          <input type="color" id="col-cvd-line" value="#38bdf8" onchange="cvdLineColor=this.value; savePrefs(); renderAllCharts();">
          <input type="color" id="col-cvd-up" value="#089981" onchange="cvdUpColor=this.value; savePrefs(); renderAllCharts();">
          <input type="color" id="col-cvd-dn" value="#f23645" onchange="cvdDnColor=this.value; savePrefs(); renderAllCharts();">
          <input type="color" id="col-cvd-bg" value="#0b0e14" onchange="cvdBgColor=this.value; savePrefs(); renderAllCharts();">
        </div>
      </div>
      <label class="set-chk" style="justify-content:space-between;"><span>Big Order Bubbles</span><input type="checkbox" id="chk-bub" checked onchange="showBubbles=this.checked; savePrefs(); renderAllCharts();"></label>
      <label class="set-chk" style="justify-content:space-between;"><span>SMC OB + PDH/PDL</span><input type="checkbox" id="chk-ob" checked onchange="showOB=this.checked; savePrefs(); renderAllCharts();"></label>
      <label class="set-chk" style="justify-content:space-between;"><span>VWAP Line</span><input type="checkbox" id="chk-vwap" checked onchange="showVWAP=this.checked; savePrefs(); renderAllCharts();"></label>
      <label class="set-chk" style="justify-content:space-between;"><span>Option Call/Put Walls</span><input type="checkbox" id="chk-walls" checked onchange="showWalls=this.checked; savePrefs(); renderAllCharts();"></label>
      <label class="set-chk" style="justify-content:space-between;"><span>Entry / SL / TP Lines</span><input type="checkbox" id="chk-plan" checked onchange="showPlan=this.checked; savePrefs(); renderAllCharts();"></label>
      <div class="set-row" style="font-size:11.5px;">
        <span>Chart & Axis Text Size (px):</span>
        <input type="number" id="lbl-font-size" value="11" min="9" max="20" style="width:55px;background:#131722;color:#fff;border:1px solid #363a45;border-radius:4px;padding:3px 6px;" onchange="labelFontSize=parseInt(this.value)||11; savePrefs(); renderAllCharts();">
      </div>
    </div>
    <hr style="border-color:#2a2e39;margin:8px 0;">
    <div style="font-size:10.5px;color:#38bdf8;font-weight:800;margin-bottom:5px;">+ BUILT-IN OVERLAY (EMA / SMA / BOLLINGER)</div>
    <div style="display:flex;gap:5px;align-items:center;margin-bottom:8px;">
      <select id="cust-ind-type" style="background:#131722;color:#fff;border:1px solid #363a45;border-radius:4px;font-size:11px;padding:5px;"><option value="EMA">EMA</option><option value="SMA">SMA</option><option value="BB">Bollinger</option></select>
      <input type="number" id="cust-ind-len" value="20" min="2" max="200" style="width:58px;background:#131722;color:#fff;border:1px solid #363a45;border-radius:4px;font-size:11px;padding:5px;">
      <input type="color" id="cust-ind-col" value="#e879f9" style="width:30px;height:28px;border:none;background:none;cursor:pointer;">
      <button class="tv-btn active" style="padding:5px 10px;" onclick="addCustomIndicator()">Add</button>
    </div>
    <div id="cust-ind-list" style="display:flex;flex-direction:column;gap:4px;margin-bottom:8px;"></div>
    <hr style="border-color:#2a2e39;margin:8px 0;">
    <div style="font-size:10.5px;color:#4ade80;font-weight:800;margin-bottom:4px;">💻 MY SCRIPT (CUSTOM FORMULA / PINE-STYLE CODE)</div>
    <input type="text" id="my-script-name" class="inp-dark" style="margin:2px 0 4px 0;padding:5px 8px;" placeholder="Script Name">
    <textarea id="my-script-code" rows="2" class="inp-dark" style="font-family:monospace;font-size:11px;margin:0 0 6px 0;" placeholder="(ema(close, 9) + ema(close, 21)) / 2"></textarea>
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <input type="color" id="my-script-col" value="#22d3ee" style="width:30px;height:26px;border:none;background:none;cursor:pointer;">
      <button class="tv-btn active" style="padding:5px 12px;" onclick="addMyCustomScript()">▶ Add My Script</button>
    </div>
  </div>
</div>

<div class="modal-bg" id="theme-modal" onclick="if(event.target===this) closeModal('theme-modal')">
  <div class="modal-box" style="max-width:300px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <b style="color:#facc15;font-size:13px;">🎨 Chart Background Theme</b>
      <button class="tv-btn" onclick="closeModal('theme-modal')">✕</button>
    </div>
    <div style="display:flex;flex-direction:column;gap:6px;">
      <button class="tv-btn" style="justify-content:flex-start;padding:7px 10px;background:#131722;color:#fff;" onclick="setChartTheme('#131722','#1e222d','#2a2e39','#d1d4dc')">🌑 TradingView Dark</button>
      <button class="tv-btn" style="justify-content:flex-start;padding:7px 10px;background:#000000;color:#fff;" onclick="setChartTheme('#000000','#0d1117','#22262e','#e5e7eb')">⬛ AMOLED Pure Black</button>
      <button class="tv-btn" style="justify-content:flex-start;padding:7px 10px;background:#0b132b;color:#fff;" onclick="setChartTheme('#0b132b','#1c2541','#3a506b','#f8fafc')">🌌 Institutional Navy</button>
      <button class="tv-btn" style="justify-content:flex-start;padding:7px 10px;background:#f1f5f9;color:#0f172a;" onclick="setChartTheme('#ffffff','#f1f5f9','#cbd5e1','#0f172a')">☀️ Classic Light White</button>
    </div>
  </div>
</div>

<div class="modal-bg" id="tv-settings-modal" onclick="if(event.target===this) closeSettingsModal()">
  <div class="tv-set-modal">
    <div class="tv-set-head"><span>Settings (Auto-Saved)</span><button class="tv-btn" onclick="closeSettingsModal()" style="font-size:15px;">✕</button></div>
    <div class="tv-set-body">
      <div class="tv-set-nav">
        <button class="set-nav-btn active" id="snav-symbol" onclick="switchSetTab('symbol')">🕯 Symbol</button>
        <button class="set-nav-btn" id="snav-status" onclick="switchSetTab('status')">☰ Status line</button>
        <button class="set-nav-btn" id="snav-scales" onclick="switchSetTab('scales')">📏 Scales & Axis</button>
        <button class="set-nav-btn" id="snav-canvas" onclick="switchSetTab('canvas')">🎨 Canvas & CVD</button>
        <button class="set-nav-btn" id="snav-trading" onclick="switchSetTab('trading')">📈 Trading</button>
        <button class="set-nav-btn" id="snav-alerts" onclick="switchSetTab('alerts')">⏰ Alerts</button>
        <button class="set-nav-btn" id="snav-events" onclick="switchSetTab('events')">📅 Events</button>
      </div>
      <div class="tv-set-content">
        <div id="stab-symbol" class="sub-view active">
          <div class="set-row"><label class="set-chk"><input type="checkbox" id="set-prev-close" onchange="tvSet.prevClose=this.checked; savePrefs(); renderAllCharts();"> Color bars based on previous close</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" id="set-body" checked onchange="tvSet.showBody=this.checked; savePrefs(); renderAllCharts();"> Body</label><div><input type="color" id="set-bull-col" value="#089981" onchange="tvSet.bullCol=this.value; savePrefs(); renderAllCharts();"> <input type="color" id="set-bear-col" value="#f23645" onchange="tvSet.bearCol=this.value; savePrefs(); renderAllCharts();"></div></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" id="set-wick" checked onchange="tvSet.showWick=this.checked; savePrefs(); renderAllCharts();"> Wick</label><div><input type="color" id="set-bull-wick" value="#089981" onchange="tvSet.bullWick=this.value; savePrefs(); renderAllCharts();"> <input type="color" id="set-bear-wick" value="#f23645" onchange="tvSet.bearWick=this.value; savePrefs(); renderAllCharts();"></div></div>
          <div class="set-row"><span>Timezone</span><select id="set-tz" onchange="tvSet.tz=this.value; savePrefs(); renderAllCharts();" style="background:#131722;color:#fff;border:1px solid #363a45;padding:4px 8px;border-radius:4px;"><option value="IST" selected>(UTC+5:30) Kolkata</option><option value="UTC">(UTC+0:00) London / UTC</option></select></div>
        </div>
        <div id="stab-status" class="sub-view">
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.stTitle=this.checked; savePrefs(); renderAllCharts();"> Symbol Title & Timeframe</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.stOHLC=this.checked; savePrefs(); renderAllCharts();"> Open / High / Low / Close Values</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.stBuySell=this.checked; savePrefs(); renderAllCharts();"> Buy / Sell Bid-Ask Buttons</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.stChips=this.checked; savePrefs(); renderAllCharts();"> Orderflow & SMC Text</label></div>
        </div>
        <div id="stab-scales" class="sub-view">
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.scLastPrice=this.checked; savePrefs(); renderAllCharts();"> Symbol Last Price Label</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.scCountdown=this.checked; savePrefs(); renderAllCharts();"> Countdown to Bar Close</label></div>
          <div class="set-row"><span>X & Y Axis Font Size (px)</span><input type="number" id="axis-font-size" value="11" min="9" max="18" style="width:55px;background:#131722;color:#fff;border:1px solid #363a45;padding:3px 6px;border-radius:4px;" onchange="axisFontSize=parseInt(this.value)||11; savePrefs(); renderAllCharts();"></div>
        </div>
        <div id="stab-canvas" class="sub-view">
          <div class="set-row"><span>Chart Background Color</span><input type="color" id="set-canvas-bg" value="#131722" onchange="setChartTheme(this.value,'#1e222d','#2a2e39', this.value==='#ffffff'?'#0f172a':'#d1d4dc');"></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.showGrid=this.checked; savePrefs(); renderAllCharts();"> Grid Lines</label><input type="color" value="#1c202b" onchange="chartGridColor=this.value; savePrefs(); renderAllCharts();"></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.watermark=this.checked; savePrefs(); renderAllCharts();"> Symbol Watermark</label></div>
        </div>
        <div id="stab-trading" class="sub-view">
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="showPlan=this.checked; document.getElementById('chk-plan').checked=this.checked; savePrefs(); renderAllCharts();"> Show Entry / Stop-Loss / TP Lines</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.tradeLabels=this.checked; savePrefs(); renderAllCharts();"> Position Price Text on Chart</label></div>
        </div>
        <div id="stab-alerts" class="sub-view">
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.alertSound=this.checked; savePrefs();"> Play Sound Alert on Hit</label></div>
        </div>
        <div id="stab-events" class="sub-view">
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="tvSet.showSessions=this.checked; savePrefs(); renderAllCharts();"> Session Killzones (London / NY)</label></div>
          <div class="set-row"><label class="set-chk"><input type="checkbox" checked onchange="showOB=this.checked; document.getElementById('chk-ob').checked=this.checked; savePrefs(); renderAllCharts();"> Previous Day High / Low (PDH/PDL)</label></div>
        </div>
      </div>
    </div>
    <div class="tv-set-foot">
      <button class="tv-btn" style="color:#f23645;" onclick="factoryResetPrefs()">Factory Reset</button>
      <button class="tv-btn active" style="padding:5px 14px;" onclick="closeSettingsModal()">Save & Ok</button>
    </div>
  </div>
</div>

<div class="modal-bg" id="add-sym-modal" onclick="if(event.target===this) closeModal('add-sym-modal')">
  <div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><b>⭐ Add Symbol to Favorite Watchlist</b><button class="tv-btn" onclick="closeModal('add-sym-modal')">✕</button></div>
    <p style="font-size:11px;color:#9ca3af;margin-bottom:6px;">Catalog se chunein ya koi bhi NSE Stock/Asset likhein (Signal sirf Favorite symbols ka banega):</p>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;max-height:110px;overflow-y:auto;">
      <button class="tv-btn active" onclick="quickFavAdd('FINNIFTY')">+ FINNIFTY</button>
      <button class="tv-btn active" onclick="quickFavAdd('RELIANCE')">+ RELIANCE</button>
      <button class="tv-btn active" onclick="quickFavAdd('HDFCBANK')">+ HDFCBANK</button>
      <button class="tv-btn active" onclick="quickFavAdd('TCS')">+ TCS</button>
      <button class="tv-btn active" onclick="quickFavAdd('INFY')">+ INFY</button>
      <button class="tv-btn active" onclick="quickFavAdd('ICICIBANK')">+ ICICIBANK</button>
      <button class="tv-btn active" onclick="quickFavAdd('SBIN')">+ SBIN</button>
      <button class="tv-btn active" onclick="quickFavAdd('USOIL')">+ USOIL</button>
      <button class="tv-btn active" onclick="quickFavAdd('NATGAS')">+ NATGAS</button>
      <button class="tv-btn active" onclick="quickFavAdd('EURUSD')">+ EURUSD</button>
      <button class="tv-btn active" onclick="quickFavAdd('US500CASH')">+ US500CASH</button>
    </div>
    <input type="text" id="new-sym-ticker" class="inp-dark" placeholder="Symbol (e.g. ZOMATO, HAL, TATAMOTORS, GBPUSD)">
    <input type="text" id="new-sym-name" class="inp-dark" placeholder="Display Name (Optional)">
    <div style="display:flex;justify-content:flex-end;gap:6px;"><button class="tv-btn" onclick="closeModal('add-sym-modal')">Cancel</button><button class="tv-btn active" onclick="submitNewSymbol()">Add to Favorites & Open</button></div>
  </div>
</div>

<div class="modal-bg" id="pc-modal" onclick="if(event.target===this) closeModal('pc-modal')">
  <div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><b>💻 Mobile ka Terminal PC Chrome par Chalayein</b><button class="tv-btn" onclick="closeModal('pc-modal')">✕</button></div>
    <div id="pc-links">Loading IP...</div>
  </div>
</div>
