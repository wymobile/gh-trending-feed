#!/usr/bin/env python3
"""Fetch GitHub trending page and write an enriched RSS feed (trending.xml).

Per item: full description (translated to Chinese), topics/homepage/fork count
via GitHub API, and trend fields computed against history.csv (rank movement,
star delta, new entries). Runs on GitHub Actions runners. Local testing:
  python3 -I scripts/build_feed.py --source saved_page.html --out test.xml
"""
import argparse
import csv
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SINCE = os.environ.get("SINCE", "daily")
LANG = os.environ.get("LANGUAGE", "")
SINCE_ZH = {"daily": "每日", "weekly": "每周", "monthly": "每月"}


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
        # anchor on the h2 title link; plain href would match sponsor links too
        # h2 is the title heading only; lazy until the first href inside it (data-hydro-click
        # attribute pushes the href ~557 chars past <h2>, so a fixed short bound fails)
        m = re.search(r'<h2[^>]*>.*?href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', block, re.S)
        if not m:
            continue
        desc = re.search(r'<p class="[^"]*">(.*?)</p>', block, re.S)
        desc = html.unescape(re.sub(r'<[^>]+>', '', desc.group(1)).strip()) if desc else ""
        stars_today = re.search(r'>([\d,]+)\s+stars\s+today', block)
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)', block)
        items.append({
            "repo": m.group(1),
            "url": "https://github.com/" + m.group(1),
            "desc": desc,
            "stars_today": stars_today.group(1) if stars_today else "",
            "lang": lang.group(1) if lang else "",
        })
    return items


def translate(text):
    if not text or os.environ.get("TRANSLATE", "true") == "false":
        return text
    for attempt in range(2):
        try:
            url = ("https://translate.googleapis.com/translate_a/single"
                   "?client=ddg&sl=auto&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=15).read())
            return "".join(seg[0] for seg in data[0] if seg[0]) or text
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(5)
                continue
            print(f"translate failed (kept original): HTTP {e.code}", file=sys.stderr)
            return text
        except Exception as e:
            print(f"translate failed (kept original): {e}", file=sys.stderr)
            return text


def api_repo(repo):
    """GitHub REST API per-repo enrichment. Returns None on any failure."""
    token = os.environ.get("GITHUB_TOKEN")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/" + repo,
            headers={"User-Agent": "trending-feed-bot",
                     "Accept": "application/vnd.github+json",
                     "Authorization": f"Bearer {token}" if token else ""},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return {"stars": data.get("stargazers_count"), "forks": data.get("forks_count"),
                "topics": data.get("topics") or [], "homepage": data.get("homepage") or "",
                "pushed_at": (data.get("pushed_at") or "")[:10],
                "desc_api": (data.get("description") or "").strip()}
    except Exception as e:
        print(f"api failed for {repo}: {e}", file=sys.stderr)
        return None


def load_history(path, today):
    """Previous-day snapshot {repo: (rank, stars)} excluding today's own rows."""
    prev = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["date"] != today:
                    try:
                        prev[row["repo"]] = (int(row["rank"]), int(row["stars"]))
                    except (ValueError, KeyError):
                        continue  # malformed/legacy row (e.g. pre-fix sponsors false positive)
    return prev


def build_desc(it, api, prev, today_rank):
    parts = []
    desc = it.get("desc_zh") or it["desc"]
    if desc:
        parts.append("功能：" + desc)
    if api:
        if api["topics"]:
            parts.append("标签：" + ", ".join(api["topics"][:6]))
        if api["homepage"]:
            parts.append("主页：" + api["homepage"])
        parts.append(f"fork {api['forks']}｜总star {api['stars']}")
    if prev.get(it["repo"]):
        prank, pstars = prev[it["repo"]]
        delta = (api["stars"] - pstars) if api and api.get("stars") is not None else None
        trend = f"昨日第{prank}→今日第{today_rank}"
        if delta is not None:
            trend += f"（star {delta:+d}）"
        parts.append("趋势：" + trend)
    else:
        parts.append("趋势：新上榜")
    if api and api["pushed_at"]:
        parts.append("最近推送：" + api["pushed_at"])
    return " ｜ ".join(filter(None, parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="local HTML file for testing instead of fetching")
    ap.add_argument("--out", default="trending.xml")
    ap.add_argument("--history", default="history.csv")
    args = ap.parse_args()

    page = fetch_html(args.source)
    items = parse_items(page)
    if not items:
        print("error: no <article> blocks parsed — page structure changed?", file=sys.stderr)
        sys.exit(1)
    print(f"parsed {len(items)} repos from {page_url()}", file=sys.stderr)

    today = datetime.datetime.now(datetime.timezone.utc)
    today_s = today.strftime("%Y-%m-%d")
    prev = load_history(args.history, today_s)

    for rank, it in enumerate(items, 1):
        it["rank"] = rank
        it["api"] = api_repo(it["repo"])
        time.sleep(0.2)
        base_desc = it["desc"] or (it["api"] or {}).get("desc_api", "")
        it["desc_zh"] = translate(base_desc)
        time.sleep(0.4)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<rss version=\"2.0\">",
        "<channel>",
        f"<title>GitHub 热榜（{SINCE_ZH.get(SINCE, SINCE)}）</title>",
        "<link>https://github.com/trending</link>",
        "<description>GitHub 每日热榜：内容+功能+趋势（趋势基于仓库内 history.csv 对比）</description>",
        f"<lastBuildDate>{today.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>",
    ]
    for it in items:
        desc = html.escape(build_desc(it, it["api"], prev, it["rank"]))
        cats = "".join(f"<category>{html.escape(t)}</category>" for t in (it["api"] or {}).get("topics", [])[:6])
        parts.append(
            "<item>"
            f"<title>{html.escape(str(it['rank']) + '. ' + it['repo'])}</title>"
            f"<link>{it['url']}</link>"
            f"<guid isPermaLink=\"false\">{html.escape(it['repo'])}-{today_s}</guid>"
            f"<pubDate>{today.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"{cats}<description>{desc}</description>"
            "</item>"
        )
    parts += ["</channel>", "</rss>", ""]
    open(args.out, "w", encoding="utf-8").write("\n".join(parts))

    # append today's snapshot (skip if today's rows already exist, for reruns)
    exists_today = os.path.exists(args.history) and any(
        row["date"] == today_s for row in csv.DictReader(open(args.history, encoding="utf-8"))
    )
    if not exists_today:
        new = not os.path.exists(args.history)
        with open(args.history, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "rank", "repo", "stars"])
            for it in items:
                stars = (it["api"] or {}).get("stars")
                if stars is None:
                    stars = int(it["stars_today"].replace(",", "") or 0)
                w.writerow([today_s, it["rank"], it["repo"], stars])
        print(f"history appended: {args.history}", file=sys.stderr)
    else:
        print(f"history unchanged (rows for {today_s} already present)", file=sys.stderr)


if __name__ == "__main__":
    main()
