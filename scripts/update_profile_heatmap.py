#!/usr/bin/env python3
"""Fetch public GitHub contribution data and render the profile heatmap."""
from __future__ import annotations

from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re

USERNAME = "bamf-venom"
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "profile-contributions.json"
SVG_PATH = ROOT / "profile-heatmap.svg"


class ContributionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = []
        self.tooltips = {}
        self.active_tooltip = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tool-tip" and attrs.get("for"):
            self.active_tooltip = attrs["for"]
            self.tooltips[self.active_tooltip] = []
        elif tag == "td" and "ContributionCalendar-day" in attrs.get("class", ""):
            day = attrs.get("data-date")
            if day:
                self.days.append({
                    "id": attrs.get("id", ""),
                    "date": day,
                    "count": int(attrs.get("data-count", "0") or 0),
                    "level": int(attrs.get("data-level", "0") or 0),
                })

    def handle_data(self, data):
        if self.active_tooltip:
            self.tooltips[self.active_tooltip].append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.active_tooltip = None


def main():
    url = f"https://github.com/users/{USERNAME}/contributions"
    request = Request(url, headers={"User-Agent": "profile-readme-heatmap/1.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(html)
    for item in parser.days:
        tooltip = " ".join(parser.tooltips.get(item["id"], []))
        count_match = re.search(r"(\d[\d,]*)\s+contributions?", tooltip, re.IGNORECASE)
        if count_match:
            item["count"] = int(count_match.group(1).replace(",", ""))
        elif re.search(r"no contributions", tooltip, re.IGNORECASE):
            item["count"] = 0

    unique = {item["date"]: item for item in parser.days}
    days = sorted(unique.values(), key=lambda item: item["date"])
    if len(days) < 300:
        raise RuntimeError(f"GitHub returned only {len(days)} contribution days; refusing to overwrite the graph.")

    end = date.fromisoformat(days[-1]["date"])
    start = end - timedelta(days=364)
    days = [item for item in days if start <= date.fromisoformat(item["date"]) <= end]
    by_date = {item["date"]: item for item in days}
    total = sum(item["count"] for item in days)
    if total == 0:
        raise RuntimeError("No contribution counts were parsed from GitHub's day tooltips; refusing to publish an empty graph.")
    start_monday = start - timedelta(days=start.weekday())

    cells = []
    for offset in range(365):
        current = start + timedelta(days=offset)
        item = by_date.get(current.isoformat(), {"count": 0, "level": 0})
        week = (current - start_monday).days // 7
        x, y = 38 + week * 14, 42 + current.weekday() * 14
        level = max(0, min(4, item["level"]))
        cells.append(
            f'<rect x="{x}" y="{y}" width="10" height="10" rx="2" '
            f'fill="{["#20252b", "#34413a", "#527b5c", "#79b982", "#a7e6a1"][level]}" '
            f'data-date="{current.isoformat()}" data-count="{item["count"]}">'
            f'<title>{item["count"]} contributions on {current.isoformat()}</title>'
            f'<animate attributeName="opacity" from="0.15" to="1" dur="0.45s" '
            f'begin="{min(week * 0.012, 0.6):.3f}s" fill="freeze"/></rect>'
        )

    month_labels = []
    seen = set()
    for item in days:
        current = date.fromisoformat(item["date"])
        key = (current.year, current.month)
        if current.day <= 7 and key not in seen:
            seen.add(key)
            week = ((current - start_monday).days // 7)
            month_labels.append(
                f'<text x="{38 + week * 14}" y="31" fill="#8b949e" font-size="10">'
                f'{current.strftime("%b")}</text>'
            )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="158" viewBox="0 0 820 158" role="img" aria-label="{total} GitHub contributions in the last year">
<rect width="820" height="158" rx="10" fill="#0d1117"/>
<text x="24" y="21" fill="#c9d1d9" font-family="monospace" font-size="12">{total:,} contributions in the last year</text>
{''.join(month_labels)}
{''.join(cells)}
<text x="38" y="151" fill="#8b949e" font-family="monospace" font-size="9">LESS</text>
<rect x="72" y="142" width="10" height="10" rx="2" fill="#20252b"/><rect x="86" y="142" width="10" height="10" rx="2" fill="#34413a"/><rect x="100" y="142" width="10" height="10" rx="2" fill="#527b5c"/><rect x="114" y="142" width="10" height="10" rx="2" fill="#79b982"/><rect x="128" y="142" width="10" height="10" rx="2" fill="#a7e6a1"/>
<text x="148" y="151" fill="#8b949e" font-family="monospace" font-size="9">MORE</text>
</svg>
'''
    DATA_PATH.write_text(json.dumps({"username": USERNAME, "days": days}, indent=2) + "\n", encoding="utf-8")
    SVG_PATH.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
