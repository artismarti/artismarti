import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROFILE_URL = "https://www.goodreads.com/user/show/40441560"
START_TAG = "<!-- GOODREADS-LIST:START -->"
END_TAG = "<!-- GOODREADS-LIST:END -->"


class CurrentlyReadingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section_depth = 0
        self.capture = None
        self.text = []
        self.books = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.section_depth:
                self.section_depth += 1
            elif attrs.get("id") == "currentlyReadingReviews":
                self.section_depth = 1
        if not self.section_depth or tag != "a":
            return
        classes = attrs.get("class", "").split()
        if "bookTitle" in classes:
            url = urljoin(PROFILE_URL, attrs.get("href", ""))
            if not url.startswith("https://www.goodreads.com/book/show/"):
                raise ValueError("Unexpected Goodreads book URL")
            self.books.append({"url": url})
            self.capture = "title"
        elif "authorName" in classes and self.books:
            self.capture = "author"
        self.text = []

    def handle_data(self, data):
        if self.capture:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.capture:
            self.books[-1][self.capture] = " ".join("".join(self.text).split())
            self.capture = None
        if tag == "div" and self.section_depth:
            self.section_depth -= 1


def escape_markdown(text):
    for character in "\\`*_[]<>":
        text = text.replace(character, "\\" + character)
    return text


def update_readme(readme, html):
    parser = CurrentlyReadingParser()
    parser.feed(html)
    # Keep the existing list if Goodreads changes its markup or serves a sign-in page.
    if not parser.books or any(
        not book.get("title") or not book.get("author") for book in parser.books
    ):
        raise ValueError("Could not read current books; preserving the README")
    if readme.count(START_TAG) != 1 or readme.count(END_TAG) != 1:
        raise ValueError("README must contain one pair of Goodreads markers")
    start = readme.index(START_TAG) + len(START_TAG)
    end = readme.index(END_TAG)
    if start > end:
        raise ValueError("Goodreads README markers are out of order")
    books = "\n".join(
        f"- [{escape_markdown(book['title'])}]({book['url']}) by {escape_markdown(book['author'])}"
        for book in parser.books[:2]
    )
    return readme[:start] + "\n" + books + "\n" + readme[end:]


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--html-file", type=Path)
    arguments.add_argument("--readme", type=Path, default=Path("README.md"))
    args = arguments.parse_args()
    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
    else:
        request = Request(PROFILE_URL, headers={"User-Agent": "artismarti-readme-updater"})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
    original = args.readme.read_text(encoding="utf-8")
    updated = update_readme(original, html)
    if updated != original:
        args.readme.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
