"""Resolve passive image references inside a repository, never arbitrary URLs."""

import base64
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

MAX_IMAGE_BYTES = 524_288
MAX_IMAGE_PATHS = 128
MAX_TOTAL_IMAGE_BYTES = 8_388_608
MAX_PREVIEW_IMAGE_CHARACTERS = 1_048_576


def repository_image_path(template_path: str, reference: str) -> str | None:
    """Root-relative and document-relative references share the repository root."""
    if not reference or len(reference) > 4096 or any(ord(c) < 32 for c in reference):
        return None
    try:
        url = urlsplit(reference)
        path = unquote(url.path, errors="strict")
    except ValueError, UnicodeError:
        return None
    if (
        url.scheme
        or url.netloc
        or reference.startswith("//")
        or not path
        or "\\" in path
        or "%" in path
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
    ):
        return None
    parts = [] if path.startswith("/") else template_path.split("/")[:-1]
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part == ".git":
            return None
        else:
            parts.append(part)
    result = "/".join(parts)
    return result if result.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) else None


def image_data_uri(content: bytes) -> str | None:
    """Only bounded raster signatures may become embedded image data."""
    if not content or len(content) > MAX_IMAGE_BYTES:
        return None
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif content.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        return None
    return f"data:{mime};base64," + base64.b64encode(content).decode("ascii")


def is_image_data_uri(value: str) -> bool:
    """Defend the rendering boundary even if cached data is malformed."""
    if len(value) > MAX_IMAGE_BYTES * 4 // 3 + 64:
        return False
    header, separator, encoded = value.partition(",")
    if not separator or header not in {
        "data:image/png;base64",
        "data:image/jpeg;base64",
        "data:image/gif;base64",
        "data:image/webp;base64",
    }:
        return False
    try:
        return image_data_uri(base64.b64decode(encoded, validate=True)) == value
    except ValueError:
        return False


class _ImageReferences(HTMLParser):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is not None and (name == "background" or (tag == "img" and name == "src")):
                path = repository_image_path(self.path, value)
                if path is not None and len(self.paths) < MAX_IMAGE_PATHS:
                    self.paths.add(path)


def referenced_images(path: str, content: bytes) -> set[str]:
    parser = _ImageReferences(path)
    parser.feed(content.decode("utf-8"))
    parser.close()
    return parser.paths
