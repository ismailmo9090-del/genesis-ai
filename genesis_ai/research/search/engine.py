"""Web search engine using DuckDuckGo HTML endpoint with rate limiting."""

import re
import time
import logging
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse
from collections import deque
from typing import Optional

import requests

from genesis_ai.config.settings import MAX_WEB_REQUESTS_PER_HOUR, OFFLINE_MODE

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_name: str = ""


class _DDGResultParser(HTMLParser):
    """Parse DuckDuckGo HTML search results."""

    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._current_result: dict = {}
        self._capture = None
        self._depth = 0
        self._in_result = False
        self._in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        href = attrs_dict.get("href", "")

        if tag == "a" and "result__a" in cls:
            self._current_result["url"] = href
            self._capture = "title"
            self._depth = 0
            self._in_result = True
        elif tag == "a" and "result__snippet" in cls:
            self._capture = "snippet"
            self._depth = 0
            self._in_snippet = True
        elif tag == "span" and "result__url__domain" in cls:
            self._capture = "domain"
            self._depth = 0

        if self._capture:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._capture:
            self._depth -= 1
            if self._depth <= 0:
                self._capture = None

    def handle_data(self, data):
        if self._capture == "title":
            self._current_result.setdefault("title", "")
            self._current_result["title"] += data.strip()
        elif self._capture == "snippet":
            self._current_result.setdefault("snippet", "")
            self._current_result["snippet"] += data.strip()
        elif self._capture == "domain":
            self._current_result.setdefault("source_name", "")
            self._current_result["source_name"] += data.strip()

    def finalize(self):
        if self._current_result.get("title") and self._current_result.get("url"):
            url = self._current_result["url"]
            if url.startswith("/l/"):
                url = ""
            source = self._current_result.get("source_name", "")
            if not source:
                try:
                    source = urlparse(url).netloc
                except Exception:
                    source = ""
            self.results.append(SearchResult(
                title=self._current_result["title"].strip(),
                url=url,
                snippet=self._current_result.get("snippet", "").strip(),
                source_name=source,
            ))
        self._current_result = {}


class _TextExtractor(HTMLParser):
    """Extract readable text from HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg", "head"}
    BLOCK_TAGS = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        raw = re.sub(r'\n\s*\n', '\n', raw)
        raw = re.sub(r' +', ' ', raw)
        return raw.strip()


class WebSearchEngine:
    """Search the web via DuckDuckGo lite endpoint with rate limiting."""

    DDG_URL = "https://lite.duckduckgo.com/lite/"

    def __init__(self, max_requests_per_hour: int = MAX_WEB_REQUESTS_PER_HOUR):
        self.max_requests_per_hour = max_requests_per_hour
        self._request_times: deque[float] = deque()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def _prune_old_requests(self):
        now = time.time()
        cutoff = now - 3600
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

    def _check_rate_limit(self) -> bool:
        self._prune_old_requests()
        return len(self._request_times) < self.max_requests_per_hour

    def _record_request(self):
        self._request_times.append(time.time())

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if OFFLINE_MODE:
            return []
        if not self._check_rate_limit():
            logger.warning("Rate limit reached (%d requests/hour). Skipping search.", self.max_requests_per_hour)
            return []
        try:
            return self._do_search(query, max_results)
        except Exception as e:
            logger.error("Search failed for '%s': %s", query, e)
            return []

    def _do_search(self, query: str, max_results: int) -> list[SearchResult]:
        instant = self._instant_answer(query)
        if instant:
            return instant[:max_results]

        # Try simplified version: remove common question words (language-agnostic approach)
        simplified = re.sub(r'\b(kya|hai|kaun|kaise|kahan|kyu|batao|samjhao|mujhe|what|how|who|where|when|why|tell|me|about|the|is|are|can)\b', '', query, flags=re.IGNORECASE).strip()
        simplified = re.sub(r'\s+', ' ', simplified).strip()
        if simplified and simplified != query and len(simplified) > 3:
            instant = self._instant_answer(simplified)
            if instant:
                return instant[:max_results]

        for attempt in range(2):
            try:
                resp = self._session.post(
                    self.DDG_URL,
                    data={"q": query, "kl": "us-en"},
                    timeout=15,
                )
                self._record_request()
                if resp.status_code == 200 and "result-link" in resp.text:
                    results = self._parse_lite_results(resp.text)
                    if results:
                        return results[:max_results]
                if resp.status_code == 202:
                    time.sleep(2)
                    continue
                break
            except Exception as e:
                logger.error("Search attempt %d failed: %s", attempt + 1, e)
                time.sleep(1)
        return []

    def _instant_answer(self, query: str) -> list[SearchResult]:
        try:
            resp = self._session.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=10,
            )
            self._record_request()
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            abstract = data.get("Abstract", "")
            abstract_url = data.get("AbstractURL", "")
            if abstract and abstract_url:
                results.append(SearchResult(
                    title=data.get("Heading", query),
                    url=abstract_url,
                    snippet=abstract[:300],
                    source_name="DuckDuckGo Instant Answer",
                ))
            answer = data.get("Answer", "")
            answer_url = data.get("AnswerURL", "")
            if answer and not abstract:
                results.append(SearchResult(
                    title=query.title(),
                    url=answer_url or "https://duckduckgo.com",
                    snippet=answer[:300],
                    source_name="DuckDuckGo Instant Answer",
                ))
            for related in data.get("RelatedTopics", [])[:3]:
                if isinstance(related, dict) and related.get("Text"):
                    results.append(SearchResult(
                        title=related.get("Text", "")[:80],
                        url=related.get("FirstURL", ""),
                        snippet=related.get("Text", "")[:200],
                        source_name="DuckDuckGo Related",
                    ))
            return results
        except Exception as e:
            logger.error("Instant answer failed: %s", e)
            return []

    def _parse_html_results(self, html: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        result_blocks = re.split(r'<div[^>]*class="[^"]*result\s+results_links[^"]*"', html)
        for block in result_blocks[1:]:
            title_match = re.search(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                block, re.DOTALL,
            )
            if not title_match:
                continue
            url = title_match.group(1)
            title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
            snippet_match = re.search(
                r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
                block, re.DOTALL,
            )
            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
            try:
                source_name = urlparse(url).netloc
            except Exception:
                source_name = ""
            if title and url and not url.startswith("/l/"):
                results.append(SearchResult(
                    title=title, url=url, snippet=snippet, source_name=source_name,
                ))
        return results

    def _parse_lite_results(self, html: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        from urllib.parse import unquote

        result_pattern = re.compile(
            r"<a([^>]*?)class='result-link'[^>]*?>(.*?)</a>",
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r"result-snippet[^>]*>(.*?)</td>",
            re.DOTALL,
        )
        domain_pattern = re.compile(
            r"<span class='link-text'>(.*?)</span>",
        )

        title_matches = result_pattern.findall(html)
        snippet_matches = snippet_pattern.findall(html)
        domain_matches = domain_pattern.findall(html)

        for i, (attrs, raw_title) in enumerate(title_matches):
            href_match = re.search(r'href="([^"]+)"', attrs)
            if not href_match:
                continue
            raw_url = href_match.group(1)
            uddg_match = re.search(r'uddg=(https%3A[^&]+)', raw_url)
            if uddg_match:
                url = unquote(uddg_match.group(1))
            elif raw_url.startswith('http'):
                url = raw_url
            else:
                continue
            title = re.sub(r'<[^>]+>', '', raw_title).strip()
            title = title.replace('&amp;', '&').replace('&quot;', '"')
            snippet = ""
            if i < len(snippet_matches):
                snippet = re.sub(r'<[^>]+>', '', snippet_matches[i]).strip()
                snippet = snippet.replace('&amp;', '&').replace('&#x27;', "'")
            source_name = ""
            if i < len(domain_matches):
                source_name = domain_matches[i].strip()
            if not source_name:
                try:
                    source_name = urlparse(url).netloc
                except Exception:
                    source_name = ""
            if title and url:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_name=source_name,
                ))
        return results

    def _parse_fallback(self, html: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        seen = set()
        for url, raw_title in links:
            title = re.sub(r'<[^>]+>', '', raw_title).strip()
            if not title or len(title) < 5 or url in seen:
                continue
            if "duckduckgo.com" in url:
                continue
            seen.add(url)
            try:
                source_name = urlparse(url).netloc
            except Exception:
                source_name = ""
            results.append(SearchResult(
                title=title,
                url=url,
                snippet="",
                source_name=source_name,
            ))
            if len(results) >= 10:
                break
        return results

    def extract_text_from_url(self, url: str, timeout: int = 15) -> str:
        if OFFLINE_MODE:
            return ""
        if not self._check_rate_limit():
            logger.warning("Rate limit reached. Skipping URL fetch.")
            return ""
        try:
            resp = self._session.get(url, timeout=timeout, allow_redirects=True)
            self._record_request()
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ""
            html = resp.text
            extractor = _TextExtractor()
            extractor.feed(html)
            return extractor.get_text()
        except Exception as e:
            logger.error("Failed to extract text from %s: %s", url, e)
            return ""

    def is_online(self) -> bool:
        try:
            resp = self._session.get("https://duckduckgo.com", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
