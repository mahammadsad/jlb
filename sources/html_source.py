from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from processing.models import DiscoveredItem, NoticeCategory
from sources.base import BaseSource, source_url_is_allowed


class HTMLSource(BaseSource):
    """Configuration-driven parser; it refuses to guess site selectors."""

    def parse(self, content: bytes, base_url: str) -> list[DiscoveredItem]:
        if not all((self.config.item_selector, self.config.title_selector, self.config.link_selector)):
            raise ValueError(f"{self.config.name} has no verified HTML selectors")
        soup = BeautifulSoup(content, "lxml")
        categories = [NoticeCategory(value) for value in self.config.categories]
        results: list[DiscoveredItem] = []
        for node in soup.select(self.config.item_selector):
            title_node = node.select_one(self.config.title_selector)
            link_node = node.select_one(self.config.link_selector)
            if not title_node or not link_node or not link_node.get("href"):
                continue
            link = urljoin(base_url, link_node["href"])
            if not source_url_is_allowed(link, self.config.allowed_domains):
                continue
            summary_node = (
                node.select_one(self.config.summary_selector)
                if self.config.summary_selector
                else None
            )
            date_node = (
                node.select_one(self.config.date_selector)
                if self.config.date_selector
                else None
            )
            summary = (
                summary_node.get_text(" ", strip=True)
                if summary_node
                else node.get_text("\n", strip=True)
            )
            if date_node:
                published_date = date_node.get_text(" ", strip=True)
                if published_date and published_date not in summary:
                    summary = f"{summary}\nPublished: {published_date}"
            results.append(
                DiscoveredItem(
                    title=title_node.get_text(" ", strip=True),
                    discovery_url=link,
                    source_name=self.config.name,
                    source_domain=urlparse(link).hostname or "",
                    category_hints=categories,
                    summary=summary[:10000],
                    candidate_official_links=[link] if self.config.official else [],
                    official=self.config.official,
                    discovery_only=self.config.discovery_only,
                )
            )
        return results
