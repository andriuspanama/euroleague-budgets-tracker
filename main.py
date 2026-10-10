#!/usr/bin/env python3
"""
EuroLeague + EuroCup + BCL + National Leagues Budgets Tracker
Veikia per GitHub Actions. Rezultatus rašo į reports/ kaip Markdown.
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ====================== KONFIGŪRACIJA ======================

WEB_SOURCES = [
    "https://basketnews.com/news-256534-euroleague-teams-budgets-2026-27-payrolls.html",
    "https://sportando.basketball/en/euroleague-budgets-panathinaikos-leads-with-e34m-net-payroll/",
    "https://www.eurohoops.net/en/proa/2017378/paris-leads-french-league-budgets-ahead-of-asvel/",
    "https://basketmagazine.net/budget-euroleague-2026-27-panathinaikos-milano-virtus/",
]

# Platesnis X account'ų sąrašas (biudžetai, sutartys, atlyginimai, transferai)
X_INSIDERS = [
    # Pagrindiniai biudžetų šaltiniai
    "BasketNews_com",
    "DonatasUrbonas",
    "Eurohoopsnet",
    "ArisBarkas",
    "Carchia",
    "Sportando",
    "Headliners_fr",
    # Transferai + insideriai
    "EuroBallin",
    "BSphere_",
    "totalbasketeu",
    "EurohoopsTR",
    "Nikola_Milorad",
    "GiannisAskounis",
    # Regioniniai
    "BeBasket_fr",
    "BasketEurope",
    "EBasketbolu",
    "fanzonebasket",
    "backdoor_pod",
]

BUDGET_KEYWORDS = [
    "budget", "biudžetas", "presupuesto", "bilancio", "etat", "masse salariale",
    "payroll", "salaries", "monte ingaggi", "maaş", "bütçe", "stipendi",
    "net payroll", "gross payroll", "total budget", "budget total",
    "€", "eur", "million", "mln", "m€", "milioni", "millones", "milyon",
    "contract", "sutartis", "deal", "agreement"
]

X_SEARCH_QUERY = (
    '(budget OR biudžetas OR presupuesto OR bilancio OR "net payroll" OR "total budget" OR bütçe OR maaş OR "masse salariale" OR "monte ingaggi" OR salary OR salaries OR contract) '
    '(Panathinaikos OR Olympiacos OR PAO OR AEK OR Aris OR PAOK OR Promitheas OR Peristeri OR '
    '"Real Madrid" OR Barcelona OR Barça OR Valencia OR Baskonia OR Unicaja OR Joventut OR Murcia OR Tenerife OR '
    'Bayern OR "Alba Berlin" OR Alba OR Ulm OR Bonn OR '
    'Milano OR "Olimpia Milano" OR Virtus OR "Virtus Bologna" OR Tortona OR Venezia OR Trento OR '
    'Fenerbahce OR Fenerbahçe OR "Anadolu Efes" OR Efes OR Besiktas OR Beşiktaş OR Galatasaray OR '
    'Paris OR ASVEL OR Monaco OR Bourg OR Strasbourg OR "JL Bourg" OR '
    'Zalgiris OR Partizan OR "Crvena Zvezda" OR Zvezda OR Dubai OR Hapoel OR Maccabi OR '
    'EuroLeague OR EuroCup OR BCL OR "Champions League" OR "FIBA Europe Cup") '
    '(2026 OR 2027) -is:retweet'
)

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
    return relevant[:5]


def scrape_web() -> List[Dict[str, Any]]:
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BudgetTracker/1.0)"}

    for url in WEB_SOURCES:
        print(f"Scrapinu: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            title = clean_text(soup.title.get_text()) if soup.title else ""
            paragraphs = soup.select("article p") or soup.select("p")
            text = " ".join(p.get_text() for p in paragraphs)
            mentions = extract_budget_mentions(text)

            results.append({
                "source": "web",
                "title": title,
                "url": url,
                "mentions": mentions,
                "preview": clean_text(text)[:250]
            })
        except Exception as e:
            print(f"  Klaida: {e}")
            results.append({"source": "web", "url": url, "error": str(e)})

    return results


def get_x_client():
    import tweepy
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        print("ĮSPĖJIMAS: Nėra X_BEARER_TOKEN. X paieška bus praleista.")
        return None
    return tweepy.Client(bearer_token=token, wait_on_rate_limit=True)


def scrape_x_search(max_results: int = 50) -> List[Dict[str, Any]]:
    client = get_x_client()
    if not client:
        return []

    results = []
    print("Ieškau X...")

    try:
        resp = client.search_recent_tweets(
            query=X_SEARCH_QUERY,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "author_id", "public_metrics", "text"],
            expansions=["author_id"],
            user_fields=["username", "name"]
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
                "created_at": tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "",
                "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                "url": f"https://x.com/{username}/status/{tweet.id}"
            })
    except Exception as e:
        print(f"X paieškos klaida: {e}")

    return results


def scrape_x_insiders(max_per_user: int = 8) -> List[Dict[str, Any]]:
    client = get_x_client()
    if not client:
        return []

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
                if not any(kw in text.lower() for kw in ["budget", "payroll", "€", "million", "mln", "biudžet", "presupuesto", "bilancio", "bütçe", "maaş", "masse salariale", "monte ingaggi", "salary", "contract", "deal"]):
                    continue
                mentions = extract_budget_mentions(text)
                results.append({
                    "source": "x_insider",
                    "username": username,
                    "text": clean_text(text),
                    "mentions": mentions,
                    "created_at": tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "",
                    "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                    "url": f"https://x.com/{username}/status/{tweet.id}"
                })
        except Exception as e:
            print(f"  @{username} klaida: {e}")

    return results


def generate_markdown_report(web_results, x_search_results, insider_results) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    lines.append(f"# Biudžetų ataskaita – {now}")
    lines.append("")
    lines.append(f"**Sugeneruota:** {now}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 📰 Straipsniai")
    lines.append("")
    if not web_results:
        lines.append("_Nerasta._")
    else:
        for item in web_results:
            if item.get("error"):
                lines.append(f"- Klaida: {item.get('url')} → {item.get('error')}")
                continue
            lines.append(f"### {item.get('title', 'Be pavadinimo')}")
            lines.append(f"- Šaltinis: {item.get('url')}")
            if item.get("mentions"):
                lines.append("- **Rastos užuominos:**")
                for m in item["mentions"]:
                    lines.append(f"  - {m}")
            lines.append("")
    lines.append("")

    lines.append("## 🔍 X paieška (viešos diskusijos)")
    lines.append("")
    if not x_search_results:
        lines.append("_Nerasta aktualių įrašų._")
    else:
        for item in x_search_results:
            lines.append(f"### @{item.get('username')} ({item.get('created_at')})")
            lines.append(f"{item.get('text')}")
            lines.append(f"- Nuoroda: {item.get('url')}")
            lines.append(f"- Patiktukai: {item.get('likes', 0)}")
            if item.get("mentions"):
                lines.append("- **Ištraukos:**")
                for m in item["mentions"]:
                    lines.append(f"  - {m}")
            lines.append("")
    lines.append("")

    lines.append("## 🕵️ Žurnalistai ir insideriai")
    lines.append("")
    if not insider_results:
        lines.append("_Naujų biudžetų / sutarčių užuominų nerasta._")
    else:
        for item in insider_results:
            lines.append(f"### @{item.get('username')} ({item.get('created_at')})")
            lines.append(f"{item.get('text')}")
            lines.append(f"- Nuoroda: {item.get('url')}")
            lines.append(f"- Patiktukai: {item.get('likes', 0)}")
            if item.get("mentions"):
                lines.append("- **Ištraukos:**")
                for m in item["mentions"]:
                    lines.append(f"  - {m}")
            lines.append("")

    lines.append("---")
    lines.append("*Ataskaita sugeneruota automatiškai per GitHub Actions.*")
    return "\n".join(lines)


def main():
    print("=" * 55)
    print(f"Budget Tracker – {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 55)

    web_results = scrape_web()
    x_search_results = scrape_x_search()
    insider_results = scrape_x_insiders()

    report = generate_markdown_report(web_results, x_search_results, insider_results)

    os.makedirs("reports", exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    report_path = f"reports/budget-report-{date_str}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nAtaskaita išsaugota: {report_path}")
    print("Baigta.")


if __name__ == "__main__":
    main()
