#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.loader import load_sources  # noqa: E402
from database.supabase_repository import SupabaseRepository  # noqa: E402


SOURCE_TYPES = {
    "rss": "RSS",
    "html": "HTML",
    "json_api": "JSON_API",
    "sitemap": "SITEMAP",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_source_payload(source: dict) -> dict:
    parser = str(source.get("parser_type", "manual")).lower()
    configured_type = str(source.get("source_type") or "").upper()
    return {
        "name": source["name"],
        "slug": source.get("slug") or slugify(source["name"]),
        "source_type": configured_type or SOURCE_TYPES.get(parser, "MANUAL"),
        "parser_type": parser,
        # Production reads feed_url or base_url back as the discovery URL.
        # For configured HTML/JSON/sitemap sources this must be the audited
        # listing endpoint, not merely the site's homepage.
        "base_url": source["url"],
        "feed_url": source["url"] if parser == "rss" else None,
        "official": bool(source.get("official")),
        "discovery_only": bool(source.get("discovery_only", True)),
        "enabled": bool(source.get("enabled", False)),
        "categories": source.get("categories", []),
        "state": source.get("state"),
        "authority_type": source.get("authority_type"),
        "allowed_domains": source.get("allowed_domains", []),
        "allowed_document_domains": source.get("allowed_document_domains", []),
        "item_selector": source.get("item_selector"),
        "title_selector": source.get("title_selector"),
        "link_selector": source.get("link_selector"),
        "summary_selector": source.get("summary_selector"),
        "date_selector": source.get("date_selector"),
        "min_interval_minutes": source.get("min_interval_minutes", 120),
        "request_timeout": source.get("request_timeout", 20),
        "max_items": source.get("max_items", 20),
        "robots_status": source.get("robots_status"),
        "terms_reviewed": bool(source.get("terms_reviewed", False)),
        "selector_verified_at": source.get("selector_verified_at"),
        "notes": source.get("notes") or source.get("parser_note"),
    }


def main() -> None:
    repository = SupabaseRepository()
    count = 0
    try:
        for source in load_sources():
            repository._request(
                "POST",
                "sources",
                params={"on_conflict": "slug"},
                body=build_source_payload(source),
                prefer="resolution=merge-duplicates",
            )
            count += 1
        print(f"Source registry rows synchronized: {count}")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
