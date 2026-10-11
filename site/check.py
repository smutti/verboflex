"""Validate the public artifact, links, anchors and basic document metadata."""

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent / "dist"
EXPECTED = {
    "index.html",
    "guide.html",
    "assets/site.css",
    "assets/site.js",
    "assets/favicon.svg",
    "assets/social.png",
    ".nojekyll",
    "robots.txt",
    "sitemap.xml",
}


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.h1 = 0
        self.lang = None
        self.title = False
        self.description = False

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if "id" in attr:
            assert attr["id"] not in self.ids, f"Duplicate ID: {attr['id']}"
            self.ids.add(attr["id"])
        for key in ("src", "href"):
            if key in attr:
                self.links.append(attr[key])
        if tag == "html":
            self.lang = attr.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.title = True
        if tag == "meta" and attr.get("name") == "description":
            self.description = bool(attr.get("content"))
        if tag == "script":
            assert attr.get("src") == "assets/site.js", (
                "Only the local site script may ship"
            )
        if tag in {"script", "link", "img", "iframe"}:
            source = attr.get("src", "")
            assert not source.startswith(("http:", "https:", "//")), (
                "No third-party runtime assets"
            )


def check():
    actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file()}
    assert actual == EXPECTED, (
        f"Artifact differs from public allowlist: {actual ^ EXPECTED}"
    )
    assert not any(path.is_symlink() for path in ROOT.rglob("*")), (
        "No symlinks in artifact"
    )
    pages = {}
    for name in ("index.html", "guide.html"):
        parser = Document()
        text = (ROOT / name).read_text()
        parser.feed(text)
        assert (
            parser.lang == "en"
            and parser.h1 == 1
            and parser.title
            and parser.description
        ), name
        assert not re.search(
            r"admin@example\.com|/Users/|BEGIN (?:RSA )?PRIVATE KEY",
            text,
            re.IGNORECASE,
        ), "Private deployment content detected"
        pages[name] = parser
    for name, page in pages.items():
        for link in page.links:
            parsed = urlsplit(link)
            assert parsed.scheme not in {"javascript", "data"}, (
                f"Unexpected link scheme: {link}"
            )
            if parsed.scheme or parsed.netloc:
                continue
            assert not parsed.path.startswith("/"), (
                f"Root-absolute link breaks project Pages: {link}"
            )
            target = (ROOT / (unquote(parsed.path) or name)).resolve()
            assert target.is_relative_to(ROOT.resolve()) and target.is_file(), (
                f"Missing local link from {name}: {link}"
            )
            if parsed.fragment:
                assert (
                    target.name in pages
                    and unquote(parsed.fragment) in pages[target.name].ids
                ), f"Missing anchor from {name}: {link}"
    assert len(pages["guide.html"].ids) >= 10
    social = (ROOT / "assets/social.png").read_bytes()
    assert social[:8] == b"\x89PNG\r\n\x1a\n"
    assert (
        int.from_bytes(social[16:20], "big") == 1200
        and int.from_bytes(social[20:24], "big") == 630
    )
    ET.parse(ROOT / "sitemap.xml")
    ET.parse(ROOT / "assets/favicon.svg")
    size = sum((ROOT / name).stat().st_size for name in EXPECTED)
    assert size < 400_000, f"Unexpected artifact growth: {size} bytes"
    print(
        f"PASS: {len(EXPECTED)} allowlisted files, valid local links/anchors, English metadata, social card, no external runtime assets ({size:,} bytes)."
    )


if __name__ == "__main__":
    check()
