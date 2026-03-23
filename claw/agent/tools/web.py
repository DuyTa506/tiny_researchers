"""Web tools — search and fetch for the research agent."""

from __future__ import annotations

import asyncio
import re
from html import unescape
from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_MAX_FETCH_CHARS = 16_000
_MAX_RETRIES = 3


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo Lite."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information using DuckDuckGo. "
            "Returns relevant snippets and URLs. Use for finding facts, news, "
            "documentation, or any information not available in academic databases."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The web search query.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query: str = kwargs["query"]
        logger.info("web_search: query={!r}", query)

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.post(
                    _DUCKDUCKGO_LITE_URL,
                    data={"q": query},
                )
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPStatusError as exc:
            logger.error("DuckDuckGo HTTP error: {}", exc)
            return f"Error: DuckDuckGo returned status {exc.response.status_code}."
        except httpx.RequestError as exc:
            logger.error("DuckDuckGo request error: {}", exc)
            return f"Error: Could not reach DuckDuckGo — {exc}"
        except Exception as exc:
            logger.error("web_search unexpected error: {}", exc)
            return f"Error: Web search failed — {exc}"

        results = self._parse_results(html)
        if not results:
            return f"No web results found for: '{query}'."

        lines: list[str] = [f"Web search results for '{query}':\n"]
        for i, (title, url, snippet) in enumerate(results[:5], 1):
            lines.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

        return "\n".join(lines)

    @staticmethod
    def _parse_results(html: str) -> list[tuple[str, str, str]]:
        """Parse DuckDuckGo Lite HTML into (title, url, snippet) tuples."""
        results: list[tuple[str, str, str]] = []

        # DDG Lite wraps each result in a table structure.
        # Links are inside <a class="result-link" ...> or <a rel="nofollow" ...>
        # Snippets follow in <td class="result-snippet">
        link_pattern = re.compile(
            r'<a[^>]+href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<td\s+class="result-snippet"[^>]*>(.*?)</td>',
            re.DOTALL,
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        # Fallback: try broader link pattern if class-based one fails
        if not links:
            link_pattern_alt = re.compile(
                r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            links = link_pattern_alt.findall(html)

        for i, (url, raw_title) in enumerate(links):
            title = _strip_html(raw_title).strip()
            snippet = _strip_html(snippets[i]).strip() if i < len(snippets) else ""
            if title and url and not url.startswith("/"):
                results.append((title, url, snippet))

        return results


class WebFetchTool(Tool):
    """Fetch and read the content of a web page."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch the text content of a web page by URL. Returns up to "
            f"{_MAX_FETCH_CHARS} characters of the page's text content. "
            "Use this to read articles, documentation, or any web page."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        url: str = kwargs["url"]
        logger.info("web_fetch: url={!r}", url)

        last_error: str = ""
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=25.0,
                    follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                ) as client:
                    resp = await client.get(url)

                    # Rate limit — backoff and retry
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 0))
                        wait = retry_after if retry_after > 0 else min(10 * (2 ** attempt), 60)
                        logger.warning("web_fetch 429 rate limited, waiting {}s (attempt {})", wait, attempt + 1)
                        await asyncio.sleep(wait)
                        last_error = f"Error: URL returned status 429 (rate limited)."
                        continue

                    # Server error — backoff and retry
                    if resp.status_code >= 500:
                        wait = 5 * (attempt + 1)
                        logger.warning("web_fetch {} server error, waiting {}s (attempt {})", resp.status_code, wait, attempt + 1)
                        await asyncio.sleep(wait)
                        last_error = f"Error: URL returned status {resp.status_code}."
                        continue

                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")

                    # Return JSON as-is (for API responses)
                    if "application/json" in content_type:
                        text = resp.text
                        if len(text) > _MAX_FETCH_CHARS:
                            text = text[:_MAX_FETCH_CHARS] + f"\n\n... [truncated at {_MAX_FETCH_CHARS} chars]"
                        return f"Content from {url}:\n\n{text}"

                    if "text/html" in content_type or "text/plain" in content_type or not content_type:
                        text = resp.text
                    else:
                        return f"Error: URL returned non-text content type: {content_type}"

                    # Strip HTML and clean up
                    clean = _strip_html(text)
                    clean = re.sub(r"\n{3,}", "\n\n", clean)
                    clean = re.sub(r" {2,}", " ", clean)
                    clean = clean.strip()

                    if not clean:
                        return "Error: Page returned no readable text content."

                    if len(clean) > _MAX_FETCH_CHARS:
                        clean = clean[:_MAX_FETCH_CHARS] + f"\n\n... [truncated at {_MAX_FETCH_CHARS} chars]"

                    return f"Content from {url}:\n\n{clean}"

            except httpx.HTTPStatusError as exc:
                logger.error("web_fetch HTTP error: {}", exc)
                return f"Error: URL returned status {exc.response.status_code}."
            except httpx.RequestError as exc:
                logger.error("web_fetch request error: {}", exc)
                return f"Error: Could not fetch URL — {exc}"
            except Exception as exc:
                logger.error("web_fetch unexpected error: {}", exc)
                return f"Error: Failed to fetch URL — {exc}"

        return last_error or "Error: Failed to fetch URL after retries."


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode entities into plain text."""
    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block tags with newlines
    text = re.sub(r"<(br|p|div|li|h[1-6]|tr)[^>]*/?>", "\n", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text)
