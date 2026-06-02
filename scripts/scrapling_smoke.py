#!/usr/bin/env python3
"""Smoke-test the Scrapling scraping runtime used by ThemeMiner/Lagradar."""

from __future__ import annotations

from scrapling import Selector
from scrapling.fetchers import AsyncFetcher, DynamicFetcher, Fetcher, StealthyFetcher


def main() -> int:
    html = """
    <html>
      <body>
        <article class="company">
          <h1>Vishay Intertechnology</h1>
          <p class="business">Discrete semiconductors and passive components.</p>
        </article>
      </body>
    </html>
    """
    page = Selector(html)
    name = page.css("article.company h1::text").get()
    business = page.css(".business::text").get()
    if name != "Vishay Intertechnology" or "passive components" not in (business or ""):
        raise RuntimeError("Scrapling selector smoke test failed")
    print("scrapling parser ok")
    print("fetchers ok:", ", ".join(cls.__name__ for cls in (Fetcher, AsyncFetcher, StealthyFetcher, DynamicFetcher)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
