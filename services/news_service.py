import time
import urllib.request
import xml.etree.ElementTree as ET
import html
import re
import json
from typing import List, Dict, Any

_NEWS_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "data": []
}

_CALENDAR_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "data": []
}

NEWS_CACHE_TTL = 600       # 10 mins
CALENDAR_CACHE_TTL = 900   # 15 mins


def classify_category(title: str, desc: str) -> str:
    text = (title + " " + desc).lower()
    if any(k in text for k in ["forexfactory", "forex factory", "nfp", "fomc", "cpi", "powell", "rate hike", "interest rate", "gdp"]):
        return "FOREXFACTORY"
    elif any(k in text for k in ["cryptocraft", "crypto craft", "unlock", "tokenomics"]):
        return "CRYPTOCRAFT"
    elif any(k in text for k in ["bitcoin", "btc", "satoshi", "halving", "etf"]):
        return "BTC"
    elif any(k in text for k in ["ethereum", "eth", "solana", "sol", "altcoin", "meme", "doge", "pepe", "grass"]):
        return "ALTS"
    elif any(k in text for k in ["fed", "inflation", "cpi", "sec", "regulation", "bank", "treasury"]):
        return "MACRO"
    elif any(k in text for k in ["defi", "dex", "uniswap", "airdrop", "staking", "yield"]):
        return "DEFI"
    return "MARKET"


def get_crypto_news(force_refresh: bool = False) -> List[Dict[str, Any]]:
    global _NEWS_CACHE
    now = time.time()

    if not force_refresh and _NEWS_CACHE["data"] and (now - _NEWS_CACHE["timestamp"] < NEWS_CACHE_TTL):
        return _NEWS_CACHE["data"]

    feeds = [
        ("Cointelegraph", "https://cointelegraph.com/rss"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Decrypt", "https://decrypt.co/feed"),
        ("ForexFactory", "https://www.forexfactory.com/news.php?do=news_rss")
    ]

    collected: List[Dict[str, Any]] = []

    for name, url in feeds:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                xml_content = resp.read()
                root = ET.fromstring(xml_content)
                items = root.findall(".//item")
                for it in items[:6]:
                    raw_title = it.find("title").text if it.find("title") is not None else ""
                    raw_link = it.find("link").text if it.find("link") is not None else "#"
                    raw_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
                    raw_desc = it.find("description").text if it.find("description") is not None else ""

                    clean_title = html.unescape(raw_title or "").strip()
                    clean_desc = re.sub(r"<[^<]+?>", "", html.unescape(raw_desc or "")).strip()
                    if len(clean_desc) > 160:
                        clean_desc = clean_desc[:160] + "..."

                    cat = "FOREXFACTORY" if name == "ForexFactory" else classify_category(clean_title, clean_desc)

                    if clean_title:
                        collected.append({
                            "source": name,
                            "title": clean_title,
                            "link": clean_link.strip(),
                            "pub_date": raw_date.strip(),
                            "description": clean_desc,
                            "category": cat
                        })
        except Exception as e:
            print(f"[NEWS_SERVICE] Info: Skipping feed {name} ({e})")

    # Add CryptoCraft curated market alerts
    collected.insert(0, {
        "source": "CryptoCraft",
        "title": "CryptoCraft Live Market & Economic Calendar: High-Impact Macro Events",
        "link": "https://www.cryptocraft.com/calendar",
        "pub_date": "Live Feed",
        "description": "Track token unlocks, protocol upgrades, SEC decisions, and macro crypto-economic catalysts in real-time.",
        "category": "CRYPTOCRAFT"
    })

    if not collected and _NEWS_CACHE["data"]:
        return _NEWS_CACHE["data"]

    _NEWS_CACHE["timestamp"] = now
    _NEWS_CACHE["data"] = collected
    return collected


def get_economic_calendar(force_refresh: bool = False) -> List[Dict[str, Any]]:
    global _CALENDAR_CACHE
    now = time.time()

    if not force_refresh and _CALENDAR_CACHE["data"] and (now - _CALENDAR_CACHE["timestamp"] < CALENDAR_CACHE_TTL):
        return _CALENDAR_CACHE["data"]

    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    events_list: List[Dict[str, Any]] = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
            for ev in raw_data[:25]:
                events_list.append({
                    "title": ev.get("title", ""),
                    "country": ev.get("country", ""),
                    "date": ev.get("date", ""),
                    "impact": ev.get("impact", "Low"),
                    "forecast": ev.get("forecast", "—"),
                    "previous": ev.get("previous", "—"),
                    "link": "https://www.forexfactory.com/calendar"
                })
    except Exception as e:
        print(f"[CALENDAR_SERVICE] Notice: Calendar fallback active ({e})")

    if not events_list and _CALENDAR_CACHE["data"]:
        return _CALENDAR_CACHE["data"]
    elif not events_list:
        events_list = [
            {"title": "US CPI m/m (Inflation Rate)", "country": "USD", "impact": "High", "date": "This Week", "forecast": "0.2%", "previous": "0.3%", "link": "https://www.forexfactory.com/calendar"},
            {"title": "FOMC Meeting & Federal Funds Rate Decision", "country": "USD", "impact": "High", "date": "This Week", "forecast": "5.50%", "previous": "5.50%", "link": "https://www.forexfactory.com/calendar"},
            {"title": "Core Retail Sales m/m", "country": "USD", "impact": "High", "date": "This Week", "forecast": "0.4%", "previous": "0.2%", "link": "https://www.forexfactory.com/calendar"},
            {"title": "CryptoCraft Token Unlocks & Macro Catalyst Watch", "country": "CRYPTO", "impact": "Medium", "date": "This Week", "forecast": "Bullish", "previous": "Neutral", "link": "https://www.cryptocraft.com/calendar"},
        ]

    _CALENDAR_CACHE["timestamp"] = now
    _CALENDAR_CACHE["data"] = events_list
    return events_list
