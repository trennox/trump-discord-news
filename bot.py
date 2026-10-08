
import os
import json
import time
import html
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

FEED = "https://www.trumpstruth.org/feed"
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
STATE = Path("seen.json")


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean(raw):
    parser = TextParser()
    parser.feed(html.unescape(raw or ""))
    return " ".join("".join(parser.parts).split())


def fetch_posts():
    request = urllib.request.Request(
        FEED, headers={"User-Agent": "TrumpDiscordNews/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    posts = []
    for item in root.findall(".//item"):
        link = item.findtext("link", "").strip()
        guid = item.findtext("guid", "").strip()
        description = item.findtext("description", "")
        pubdate = item.findtext("pubDate", "")
        original = next(
            (
                child.text
                for child in item
                if child.tag.endswith("originalUrl") and child.text
            ),
            link,
        )
        posts.append({
            "id": guid or link,
            "text": clean(description),
            "url": original,
            "date": pubdate,
        })
    return [p for p in posts if p["id"]]


def send(post):
    text = post["text"] or "(Post contains media or no text)"
    text = text[:3500]
    payload = {
        "username": "Trump News",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "NEW TRUMP POST",
            "description": text,
            "url": post["url"],
            "color": 16747520,
            "fields": [{
                "name": "Published",
                "value": post["date"] or "Unknown",
                "inline": False
            }],
            "footer": {"text": "Truth Social | Automated feed"}
        }]
    }

    request = urllib.request.Request(
        WEBHOOK,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        response.read()


def main():
    posts = fetch_posts()
    if not posts:
        raise RuntimeError("Feed returned no posts")

    if not STATE.exists():
        STATE.write_text(json.dumps(
            [p["id"] for p in posts], indent=2
        ))
        print("Initialized. Existing posts skipped.")
        return

    seen = set(json.loads(STATE.read_text()))
    new_posts = [p for p in reversed(posts) if p["id"] not in seen]

    for post in new_posts:
        send(post)
        seen.add(post["id"])
        STATE.write_text(json.dumps(sorted(seen), indent=2))
        print("Published:", post["id"])
        time.sleep(1)

    print("New posts:", len(new_posts))


if __name__ == "__main__":
    main()
