#!/usr/bin/env python3
"""
WB Government Job Scraper -> Gemini (Bengali summary) -> Telegram Broadcaster
==============================================================================

Scrapes public West Bengal government job portals for new recruitment
notices, summarizes each one in Bengali using the Gemini API free tier,
and posts the result to a Telegram channel. Designed to run on a schedule
inside GitHub Actions with no external server.

Required environment variables (set as GitHub Secrets):
    TELEGRAM_BOT_TOKEN   - Bot token from @BotFather
    TELEGRAM_CHANNEL_ID  - e.g. "@your_channel" or a numeric chat id
    GEMINI_API_KEY       - API key from Google AI Studio (free tier)

Notes on target sites (checked at the time this script was written):
    - psc.wb.gov.in publishes a robots.txt that disallows automated
      crawling. This script checks robots.txt before scraping any site
      and will SKIP a site if it disallows access, logging a warning.
      That means WBPSC will be skipped by default unless its robots.txt
      changes. This is intentional -- please don't remove that check
      without reading the site's current robots.txt yourself first.
    - prb.wb.gov.in returned very little static HTML on a plain GET in
      testing; its notice list may be loaded dynamically. If it never
      yields results, inspect the live page source (view-source / dev
      tools) and adjust the parsing logic below.
    - mscwb.org is static HTML with descriptive link text and works well
      with the simple keyword-matching approach used here.
"""

import logging
import os
import sqlite3
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class LegacyTLSAdapter(HTTPAdapter):
    """
    Some Indian government servers run old/misconfigured TLS stacks that
    refuse the "safe" renegotiation modern OpenSSL insists on by default.
    This adapter opts into legacy renegotiation support -- it still does
    FULL certificate verification, it just relaxes one negotiation rule
    so we can complete a handshake with these specific servers.
    """
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

TARGET_SITES = [
    {"name": "WBPSC", "url": "https://psc.wb.gov.in/"},
    {"name": "WBPRB", "url": "https://prb.wb.gov.in/"},
    {"name": "WBMSC", "url": "https://www.mscwb.org/"},
]

# Keywords checked against combined (link text + href), case-insensitive.
# Extend this list if a site uses other recurring words (e.g. "walk-in", "exam").
KEYWORDS = ["recruitment", "vacancy", "advertisement", "notice", "pdf"]

# Link text that is almost always site-navigation, not a job posting.
JUNK_TEXT = {
    "home", "contact us", "contact", "about us", "sitemap",
    "privacy policy", "terms of use", "terms & conditions",
    "view more", "read more", "click here", "back", "next",
    "previous", "login", "sign in", "faq",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
}

DB_FILE = "jobs.db"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
GEMINI_RATE_LIMIT_DELAY = 6  # seconds -- keeps us at <=10 requests/minute on the free tier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("wb_job_scraper")


# --------------------------------------------------------------------------
# Database / deduplication layer
# --------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """Creates jobs.db (if needed) and the seen_jobs table."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            source TEXT,
            found_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def is_job_seen(conn: sqlite3.Connection, url: str) -> bool:
    cur = conn.execute("SELECT 1 FROM seen_jobs WHERE url = ? LIMIT 1", (url,))
    return cur.fetchone() is not None


def mark_job_seen(conn: sqlite3.Connection, url: str, title: str, source: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs (url, title, source) VALUES (?, ?, ?)",
        (url, title, source),
    )
    conn.commit()


# --------------------------------------------------------------------------
# robots.txt compliance
# --------------------------------------------------------------------------

def is_scraping_allowed(url: str, user_agent: str) -> bool:
    """
    Checks the target site's robots.txt before scraping it.
    If robots.txt cannot be read at all (network hiccup, no file), we
    proceed cautiously (default-allow), matching the standard robots.txt
    convention. If it explicitly disallows the path, we respect that.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        logger.warning(f"Could not read {robots_url} ({e}); proceeding cautiously.")
        return True


# --------------------------------------------------------------------------
# Gemini AI layer (Bengali summary generation)
# --------------------------------------------------------------------------

def build_gemini_prompt(title: str, source_name: str) -> str:
    return f"""You are a professional Bengali government-job news editor.

Given this English notification title from {source_name}, an official West Bengal government recruitment body:

"{title}"

Write a Telegram broadcast message STRICTLY and ENTIRELY in fluent, natural Bengali (no English words except unavoidable proper nouns). Follow this EXACT structure, keeping the emoji and Markdown bold (*text*) exactly as shown:

🚨 *নতুন সরকারি চাকরির আপডেট!* 🚨

🏢 *বিভাগ:* [department name in Bengali, inferred from the title]
💼 *পদের নাম:* [post/job name in Bengali]
🎓 *যোগ্যতা:* [likely eligibility inferred from the title, or "বিস্তারিত জানতে বিজ্ঞপ্তি দেখুন" if unclear]
📅 *আবেদনের শেষ তারিখ:* [date if present in the title, or "বিজ্ঞপ্তি দেখুন" if not]

Output ONLY the four-line block above, fully in Bengali. Do not add a preamble, explanation, the source link, or code block formatting."""


def generate_bengali_summary(title: str, source_name: str) -> str | None:
    """Calls the Gemini API and returns the Bengali summary text, or None on failure."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set.")
        return None

    payload = {
        "contents": [{"parts": [{"text": build_gemini_prompt(title, source_name)}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 400},
    }

    for attempt in range(1, 3):
        try:
            resp = requests.post(f"{GEMINI_ENDPOINT}?key={api_key}", json=payload, timeout=30)

            if resp.status_code == 429:
                logger.warning("Gemini rate-limited (429). Backing off 15s before retry...")
                time.sleep(15)
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        except (requests.exceptions.RequestException, KeyError, IndexError) as e:
            logger.error(f"Gemini API error (attempt {attempt}/2): {e}")
            time.sleep(5)

    return None


# --------------------------------------------------------------------------
# Telegram broadcast layer
# --------------------------------------------------------------------------

def send_to_telegram(message: str) -> bool:
    """Posts a message to the configured Telegram channel. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if not token or not channel_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is not set.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 400:
            # Gemini's free-form Bengali text can occasionally contain characters
            # that break Telegram's legacy Markdown parser (stray * or _).
            # Retry once as plain text so the job still gets delivered.
            logger.warning("Telegram rejected Markdown formatting; retrying as plain text.")
            payload.pop("parse_mode", None)
            resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram send failed: {e}")
        return False


# --------------------------------------------------------------------------
# Scraping layer
# --------------------------------------------------------------------------

def scrape_site(session: requests.Session, site_name: str, url: str, conn: sqlite3.Connection) -> int:
    """Scrapes one site, broadcasts any new job postings, returns count of new jobs sent."""
    if not is_scraping_allowed(url, HEADERS["User-Agent"]):
        logger.warning(f"[{site_name}] robots.txt disallows automated access to {url}. Skipping.")
        return 0

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[{site_name}] Failed to fetch {url}: {e}")
        return 0

    soup = BeautifulSoup(resp.text, "html.parser")
    anchors = soup.find_all("a", href=True)
    logger.info(f"[{site_name}] Scanned {len(anchors)} links on {url}")

    seen_this_run = set()
    new_jobs_sent = 0

    for a in anchors:
        text = a.get_text(strip=True)
        href = a["href"].strip()

        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        combined = f"{text} {href}".lower()
        if not any(kw in combined for kw in KEYWORDS):
            continue

        if text.lower() in JUNK_TEXT or len(text) < 4:
            continue

        full_url = urljoin(url, href)
        if full_url in seen_this_run:
            continue
        seen_this_run.add(full_url)

        if is_job_seen(conn, full_url):
            continue

        job_title = text if text else f"{site_name} notification"
        logger.info(f"[{site_name}] New job found: {job_title[:80]}")

        bengali_message = generate_bengali_summary(job_title, site_name)
        time.sleep(GEMINI_RATE_LIMIT_DELAY)  # always pause after a Gemini call attempt

        if not bengali_message:
            logger.warning(f"[{site_name}] Gemini failed for '{job_title[:50]}'; will retry next run.")
            continue

        final_message = f"{bengali_message}\n\n🔗 [বিস্তারিত দেখুন/আবেদন করুন]({full_url})"

        if send_to_telegram(final_message):
            mark_job_seen(conn, full_url, job_title, site_name)
            new_jobs_sent += 1
        else:
            logger.warning(f"[{site_name}] Telegram send failed for {full_url}; will retry next run.")

    return new_jobs_sent


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    required_env = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "GEMINI_API_KEY"]
    missing = [v for v in required_env if not os.environ.get(v)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(1)

    conn = init_db()
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", LegacyTLSAdapter())

    total_new = 0
    try:
        for site in TARGET_SITES:
            total_new += scrape_site(session, site["name"], site["url"], conn)
            time.sleep(2)  # be polite between sites
    finally:
        conn.close()

    logger.info(f"Run complete. {total_new} new job(s) broadcast to Telegram.")


if __name__ == "__main__":
    main()
