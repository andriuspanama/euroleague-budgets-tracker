#!/usr/bin/env python3
"""
EuroLeague Budgets Tracker 2026/27
Renka biudžetų info iš straipsnių + X/Twitter žurnalistų ir insiderių.
Apima ne tik EuroLeague, bet ir kitas tų šalių komandas.
"""

import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ====================== KONFIGŪRACIJA ======================

WEB_SOURCES = [
    "https://basketnews.com/news-256534-euroleague-teams-budgets-2026-27-payrolls.html",
    "https://sportando.basketball/en/euroleague-budgets-panathinaikos-leads-with-e34m-net-payroll/",
]

# Žurnalistai ir insideriai
X_INSIDERS = [
    "BasketNews_com",
    "DonatasUrbonas",
    "Eurohoopsnet",
    "GiannisAskounis",
    "Sportando",
    "Carchia",
    "backdoor_pod",
    "EBasketbolu",
    "fanzonebasket",
    "Headliners_fr",
]

BUDGET_KEYWORDS = [
    "budget", "biudžetas", "presupuesto", "bilancio", "etat",
    "payroll", "salaries", "monte ingaggi", "maaş", "bütçe",
    "net payroll", "gross payroll", "total budget",
    "€", "eur", "million", "mln", "m€", "milioni", "millones"
]

# Išplėsta paieška – ne tik EuroLeague, bet ir kitos tų šalių komandos
X_SEARCH_QUERY = (
    '(budget OR biudžetas OR presupuesto OR bilancio OR "net payroll" OR "total budget" OR bütçe OR maaş) '
    '(Panathinaikos OR Olympiacos OR PAO OR "Real Madrid" OR Barcelona OR Barça OR Valencia OR Baskonia OR Unicaja OR '
    'Bayern OR "Alba Berlin" OR Alba OR Milano OR "Olimpia Milano" OR Virtus OR "Virtus Bologna" OR '
    'Fenerbahce OR Fenerbahçe OR "Anadolu Efes" OR Efes OR Besiktas OR Beşiktaş OR '
    'AEK OR Aris OR PAOK OR "Promitheas" OR "Peristeri" OR '
    'Joventut OR Murcia OR Zaragoza OR Manresa OR Tenerife OR Girona OR '
    'Ulm OR Bonn OR Oldenburg OR Chemnitz OR '
    'Tortona OR Venezia OR Trento OR Varese OR '
    'Galatasaray OR "Türk Telekom" OR "Pınar Karşıyaka" OR "Bahçeşehir") '
    '(2026 OR 2027) -is:retweet'
)

# ====================== PAGALBINĖS FUNKCIJOS ======================

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_budget_mentions(text: str) -> List[str]:
    if not text:
        return []
    sentences = re.split(r"[.!?]\s+", text)
    relevant = []
    for sent in sentences:
        lower = sent.lower()
        if any(kw in lower for kw in BUDGET_KEYWORDS) and (re.search(r"\d", sent) or "€" in sent):
            relevant.append(clean_text(sent))
    return relevant[:6]


def save_results(results: List[Dict[str, Any]]):
    os.makedirs("data", exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = f"data/budgets_{date_str}.csv"
    json_path = f"data/budgets_{date_str}.json"

    if not results:
        print("Nėra rezultatų.")
        return

    pd.DataFrame(results).to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nIšsaugota: {csv_path}")
    print(f"Išsaugota: {json_path}")


# ====================== WEB SCRAPING ======================

def scrape_web() -> List[Dict[str, Any]]:
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in WEB_SOURCES:
        print(f"Scrapinu: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            title = clean_text(soup.title.get_text()) if soup.title else ""
            paragraphs = soup.select("article p") or soup.select("p")
            text = " ".join(p.get_text() for p in paragraphs)
            mentions = extract_budget_mentions(text)

            results.append({
                "source": "web",
                "url": url,
                "title": title,
                "mentions": mentions,
                "text_preview": clean_text(text)[:300],
                "scraped_at": datetime.utcnow().isoformat() + "Z"
            })
        except Exception as e:
            print(f"  Klaida: {e}")
            results.append({"source": "web", "url": url, "error": str(e)})

    return results


# ====================== X / TWITTER ======================

def get_x_client():
    import tweepy
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        raise ValueError("Nėra X_BEARER_TOKEN. Nukopijuok .env.example → .env ir įrašyk tokeną.")
    return tweepy.Client(bearer_token=token, wait_on_rate_limit=True)


def scrape_x_search(max_results: int = 30) -> List[Dict[str, Any]]:
    client = get_x_client()
    results = []
    print(f"Ieškau X: {X_SEARCH_QUERY[:80]}...")

    try:
        resp = client.search_recent_tweets(
            query=X_SEARCH_QUERY,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "author_id", "public_metrics", "text"],
            expansions=["author_id"],
            user_fields=["username"]
        )
        if not resp.data:
            return results

        users = {u.id: u for u in (resp.includes.get("users") or [])}
        for tweet in resp.data:
            user = users.get(tweet.author_id)
            username = user.username if user else "unknown"
            mentions = extract_budget_mentions(tweet.text)

            results.append({
                "source": "x_search",
                "username": username,
                "text": clean_text(tweet.text),
                "mentions": mentions,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                "url": f"https://x.com/{username}/status/{tweet.id}",
                "scraped_at": datetime.utcnow().isoformat() + "Z"
            })
    except Exception as e:
        print(f"  X paieškos klaida: {e}")

    return results


def scrape_x_insiders(max_per_user: int = 8) -> List[Dict[str, Any]]:
    client = get_x_client()
    results = []

    for username in X_INSIDERS:
        print(f"Tikrinu @{username}...")
        try:
            user = client.get_user(username=username)
            if not user.data:
                continue
            tweets = client.get_users_tweets(
                id=user.data.id,
                max_results=min(max_per_user, 100),
                tweet_fields=["created_at", "public_metrics", "text"],
                exclude=["retweets", "replies"]
            )
            if not tweets.data:
                continue

            for tweet in tweets.data:
                text = tweet.text
                if not any(kw in text.lower() for kw in ["budget", "payroll", "€", "million", "mln", "biudžet", "presupuesto", "bilancio", "bütçe", "maaş"]):
                    continue
                mentions = extract_budget_mentions(text)
                results.append({
                    "source": "x_insider",
                    "username": username,
                    "text": clean_text(text),
                    "mentions": mentions,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                    "url": f"https://x.com/{username}/status/{tweet.id}",
                    "scraped_at": datetime.utcnow().isoformat() + "Z"
                })
        except Exception as e:
            print(f"  @{username} klaida: {e}")

    return results


# ====================== MAIN ======================

def main():
    parser = argparse.ArgumentParser(description="EuroLeague Budgets Tracker")
    parser.add_argument("--web", action="store_true", help="Tik web straipsniai")
    parser.add_argument("--x", action="store_true", help="Tik X (paieška + insideriai)")
    parser.add_argument("--max", type=int, default=30, help="Max X paieškos rezultatų")
    args = parser.parse_args()

    do_all = not (args.web or args.x)
    all_results = []

    print("=" * 55)
    print(f"EuroLeague Budgets Tracker – {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    if args.web or do_all:
        print("\n[WEB] Scrapinu straipsnius...")
        all_results.extend(scrape_web())

    if args.x or do_all:
        print("\n[X] Ieškau viešose diskusijose...")
        try:
            all_results.extend(scrape_x_search(args.max))
        except Exception as e:
            print(f"X paieška neveikia: {e}")

        print("\n[X] Tikrinu žurnalistus / insiderius...")
        try:
            all_results.extend(scrape_x_insiders())
        except Exception as e:
            print(f"Insiders neveikia: {e}")

    save_results(all_results)

    # Trumpa santrauka
    print("\n" + "=" * 55)
    print("Rastos biudžetų užuominos:")
    print("=" * 55)
    for item in all_results:
        if item.get("mentions"):
            who = item.get("username") or item.get("url", "")[:40]
            for m in item["mentions"][:1]:
                print(f"• @{who}: {m[:130]}...")

    print("\nBaigta.")


if __name__ == "__main__":
    main()
