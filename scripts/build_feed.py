#!/usr/bin/env python3
"""Fetch GitHub trending page and write an RSS feed (trending.xml).

Runs on GitHub Actions runners (no proxy needed). For local testing:
  python3 -I scripts/build_feed.py --source saved_page.html --out test.xml
"""
import argparse
import datetime
import html
import os
import re
import sys
import urllib.request

SINCE = os.environ.get("SINCE", "daily")
LANG = os.environ.get("LANGUAGE", "")


def page_url():
    u = "https://github.com/trending"
    if LANG:
        u += "/" + LANG
    return u + f"?since={SINCE}"


def fetch_html(source):
    if source:
        return open(source, encoding="utf-8").read()
    req = urllib.request.Request(
        page_url(), headers={"User-Agent": "Mozilla/5.0 (compatible; trending-feed-bot)"}
    )
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def parse_items(page):
    items = []
    for block in re.findall(r'<article[^>]*>(.*?)</article>', page, re.S):
        m = re.search(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', block)
        if not m:
            continue
        repo = m.group(1)
        desc = re.search(r'<p class="[^"]*">(.*?)</p>', block, re.S)
        desc = html.unescape(re.sub(r'<[^>]+>', '', desc.group(1)).strip()) if desc else ""
        stars_today = re.search(r'>([\d,]+)\s+stars\s+today', block)
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)', block)
        items.append({
            "repo": repo,
            "url": "https://github.com/" + repo,
            "desc": desc,
            "stars_today": stars_today.group(1) if stars_today else "",
            "lang": lang.group(1) if lang else "",
        })
    return items


def build_rss(items):
    today = datetime.datetime.now(datetime.timezone.utc)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<rss version=\"2.0\">",
        "<channel>",
        "<title>GitHub Trending (daily)</title>",
        f"<link>https://github.com/trending</link>",
        "<description>GitHub daily trending repos</description>",
        f"<lastBuildDate>{today.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>",
    ]
    for it in items:
        d = " / ".join(filter(None, [it["lang"], (it["stars_today"] + " stars today") if it["stars_today"] else ""]))
        desc = html.escape((d + " | " if d else "") + it["desc"])
        parts.append(
            "<item>"
            f"<title>{html.escape(it['repo'])}</title>"
            f"<link>{it['url']}</link>"
            f"<guid isPermaLink=\"false\">{html.escape(it['repo'])}-{today.strftime('%Y-%m-%d')}</guid>"
            f"<pubDate>{today.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{desc}</description>"
            "</item>"
        )
    parts += ["</channel>", "</rss>", ""]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="local HTML file for testing instead of fetching")
    ap.add_argument("--out", default="trending.xml")
    args = ap.parse_args()

    page = fetch_html(args.source)
    items = parse_items(page)
    if not items:
        print("error: no <article> blocks parsed — page structure changed?", file=sys.stderr)
        sys.exit(1)
    print(f"parsed {len(items)} repos from {page_url()}", file=sys.stderr)
    open(args.out, "w", encoding="utf-8").write(build_rss(items))


if __name__ == "__main__":
    main()
