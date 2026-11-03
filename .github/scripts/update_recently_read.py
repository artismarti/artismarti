import argparse
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from update_currently_reading import escape_markdown


ACTIVITY_URL = "https://www.goodreads.com/user/delayable_user_show/40441560"
STATE_PATH = Path(".github/goodreads-recent.json")
START_TAG = "<!-- GOODREADS-READ-LIST:START -->"
END_TAG = "<!-- GOODREADS-READ-LIST:END -->"


class ActivityParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []
        self.event = None
        self.capture = None
        self.text = []
        self.action_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "tr" and "update" in classes:
            if self.event is not None:
                self.events.append(self.event)
            self.event = {"timestamp": attrs.get("data-timestamp", "")}
            self.action_depth = 0
            self.capture = None
        if self.event is None:
            return
        if tag == "div":
            if self.action_depth:
                self.action_depth += 1
            elif "updateAction" in classes:
                self.action_depth = 1
                self.event["action"] = ""
        if self.action_depth and "staticStars" in classes:
            ratings = {"did not like it": 1, "it was ok": 2, "liked it": 3, "really liked it": 4, "it was amazing": 5}
            if attrs.get("title") in ratings:
                self.event["rating"] = ratings[attrs["title"]]
        if tag == "a" and "bookTitle" in classes:
            match = re.match(r"^/book/show/(\d+)", attrs.get("href", ""))
            if not match:
                raise ValueError("Unexpected Goodreads activity book URL")
            self.event["id"] = match[1]
            self.event["url"] = "https://www.goodreads.com" + attrs["href"]
            self.capture = "title"
            self.text = []
        elif tag == "a" and "authorName" in classes:
            self.capture = "author"
            self.text = []

    def handle_data(self, data):
        if self.action_depth:
            self.event["action"] += data
        if self.capture:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.capture:
            self.event[self.capture] = " ".join("".join(self.text).split())
            self.capture = None
        if tag == "div" and self.action_depth:
            self.action_depth -= 1

    def close(self):
        super().close()
        if self.event is not None:
            self.events.append(self.event)
            self.event = None


def update_recent(readme, saved, html):
    parser = ActivityParser()
    parser.feed(html)
    parser.close()
    if not parser.events:
        raise ValueError("Could not read Goodreads activity; preserving saved books")
    books = {book["id"]: dict(book) for book in saved}
    for event in parser.events:
        if "finished reading" not in event.get("action", "").lower():
            continue
        if any(not event.get(key) for key in ["id", "title", "author", "timestamp"]):
            raise ValueError("Incomplete finished-reading event")
        finished = datetime.strptime(event["timestamp"], "%B %d, %Y %H:%M").date().isoformat()
        previous = books.get(event["id"])
        if previous is None or finished > previous["finished"]:
            books[event["id"]] = {key: event[key] for key in ["id", "title", "author", "url"]}
            books[event["id"]]["finished"] = finished
            if previous and "rating" in previous:
                books[event["id"]]["rating"] = previous["rating"]
    # Ratings can update known finished books, but cannot qualify a book as finished.
    for event in sorted(parser.events, key=lambda event: datetime.strptime(event["timestamp"], "%B %d, %Y %H:%M")):
        if event.get("id") in books and "rating" in event:
            books[event["id"]]["rating"] = round(event["rating"], 1)
    recent = sorted(books.values(), key=lambda book: book["finished"], reverse=True)[:3]
    if readme.count(START_TAG) != 1 or readme.count(END_TAG) != 1:
        raise ValueError("README must contain one pair of recently read markers")
    start = readme.index(START_TAG) + len(START_TAG)
    end = readme.index(END_TAG)
    if start > end:
        raise ValueError("Recently read markers are out of order")
    lines = []
    for book in recent:
        rating = f" (⭐ {book['rating']:g}/5)" if "rating" in book else ""
        lines.append(f"- [{escape_markdown(book['title'])}]({book['url']}) by {escape_markdown(book['author'])}{rating}")
    return readme[:start] + "\n" + "\n".join(lines) + "\n" + readme[end:], recent


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--html-file", type=Path)
    args = arguments.parse_args()
    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
    else:
        request = Request(ACTIVITY_URL, headers={"User-Agent": "artismarti-readme-updater"})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
    readme = Path("README.md")
    updated, recent = update_recent(readme.read_text(encoding="utf-8"), json.loads(STATE_PATH.read_text()), html)
    readme.write_text(updated, encoding="utf-8")
    STATE_PATH.write_text(json.dumps(recent, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
