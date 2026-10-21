"""Conservative, local text location on the exact rendered PNG; never a second build."""

import csv
import io
import json
import os
import re
import struct
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from verboflex.localization.code_keys.capture import CaptureBundle
from verboflex.schemas.screenshots import ScreenshotLocation, ScreenshotRegion

MAX_TSV_BYTES = 2 * 1024 * 1024
LANGUAGES = {"en": "eng", "it": "ita", "de": "deu", "es": "spa", "fr": "fra", "nl": "nld"}


@dataclass(frozen=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    line: tuple[str, ...]


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())


def match_text(tsv: str, texts: set[str], width: int, height: int) -> ScreenshotLocation:
    """Require a complete high-confidence match, with contiguous visual lines."""
    if len(tsv.encode()) > MAX_TSV_BYTES or len(tsv.splitlines()) > 10000:
        return ScreenshotLocation(status="unavailable")
    words: list[Word] = []
    try:
        for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
            if row["level"] != "5" or not row["text"].strip():
                continue
            word = Word(
                text=row["text"],
                left=int(row["left"]),
                top=int(row["top"]),
                width=int(row["width"]),
                height=int(row["height"]),
                confidence=float(row["conf"]),
                line=tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num")),
            )
            if not (
                0 <= word.left < width
                and 0 <= word.top < height
                and 0 < word.width <= width - word.left
                and 0 < word.height <= height - word.top
            ):
                return ScreenshotLocation(status="unavailable")
            words.append(word)
    except KeyError, TypeError, ValueError, csv.Error:
        return ScreenshotLocation(status="unavailable")
    stream = [(token, index) for index, word in enumerate(words) for token in tokens(word.text)]
    matches: dict[tuple[int, ...], list[ScreenshotRegion]] = {}
    for text in texts:
        target = tokens(text)
        if not target or len(target) > 500:
            continue
        for start in range(len(stream) - len(target) + 1):
            if stream[start][0] != target[0]:
                continue
            sample = stream[start : start + len(target)]
            if [token for token, _ in sample] != target:
                continue
            indices = tuple(dict.fromkeys(index for _, index in sample))
            # A substring of one OCR word is not evidence for a separate UI label.
            if (start and stream[start - 1][1] == indices[0]) or (
                start + len(target) < len(stream) and stream[start + len(target)][1] == indices[-1]
            ):
                continue
            selected = [words[index] for index in indices]
            if any(not (75 <= word.confidence <= 100) for word in selected):
                continue
            lines: dict[tuple[str, ...], list[Word]] = {}
            for word in selected:
                lines.setdefault(word.line, []).append(word)
            if len(lines) > 20:
                continue
            if any(
                nxt.left < prev.left
                or nxt.left - (prev.left + prev.width) > 3 * max(prev.height, nxt.height)
                for line in lines.values()
                for prev, nxt in zip(line, line[1:], strict=False)
            ):
                continue
            boxes = []
            for line in lines.values():
                left, top = min(w.left for w in line), min(w.top for w in line)
                right, bottom = (
                    max(w.left + w.width for w in line),
                    max(w.top + w.height for w in line),
                )
                boxes.append((left, top, right, bottom))
            # Reject matches assembled from unrelated areas of the image.
            if any(
                nxt[1] < prev[1] or nxt[1] - prev[3] > 2 * max(prev[3] - prev[1], nxt[3] - nxt[1])
                for prev, nxt in zip(boxes, boxes[1:], strict=False)
            ):
                continue
            matches[indices] = [
                ScreenshotRegion(
                    x=left / width,
                    y=top / height,
                    width=(right - left) / width,
                    height=(bottom - top) / height,
                )
                for left, top, right, bottom in boxes
            ]
    if len(matches) > 1:
        return ScreenshotLocation(status="ambiguous")
    if matches:
        return ScreenshotLocation(status="found", regions=next(iter(matches.values())))
    return ScreenshotLocation(status="not_found")


def locate_text(image: bytes, inputs: dict[str, object]) -> ScreenshotLocation:
    """A bounded optional worker step; failure never discards a valid screenshot."""
    unavailable = ScreenshotLocation(status="unavailable")
    try:
        bundle = CaptureBundle.model_validate(inputs)
        language = LANGUAGES.get(bundle.language.split("-")[0])
        if not bundle.target_key or language is None:
            return unavailable
        effective: dict[tuple[str, str], str] = {}
        for locale in dict.fromkeys((bundle.base_language, bundle.language)):
            for value in bundle.values:
                if value.language == locale:
                    effective[(value.key, json.dumps(value.selector, sort_keys=True))] = value.text
        selected = {
            selector: text
            for (key, selector), text in effective.items()
            if key == bundle.target_key
        }
        if not selected or len(selected) > 20 or sum(map(len, selected.values())) > 65536:
            return unavailable
        target_tokens = {tuple(tokens(text)) for text in selected.values()} - {()}
        if any(
            tuple(tokens(text)) in target_tokens
            for (key, _), text in effective.items()
            if key != bundle.target_key
        ):
            # A unique visual match can still belong to a different, identically named control.
            return ScreenshotLocation(status="ambiguous")
        width, height = struct.unpack(">II", image[16:24])
        with tempfile.TemporaryDirectory(prefix="verboflex-location-") as directory:
            source, output = Path(directory) / "image.png", Path(directory) / "words.tsv"
            source.write_bytes(image)
            environment = {
                key: os.environ[key] for key in ("PATH", "TESSDATA_PREFIX") if key in os.environ
            }
            environment["OMP_THREAD_LIMIT"] = "1"
            with output.open("wb") as stream:
                subprocess.run(
                    ["tesseract", str(source), "stdout", "-l", language, "--psm", "11", "tsv"],
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.DEVNULL,
                    env=environment,
                    timeout=5,
                    check=True,
                )
            if output.stat().st_size > MAX_TSV_BYTES:
                return unavailable
            return match_text(output.read_text(), set(selected.values()), width, height)
    except Exception:
        # No logs or OCR text leave the worker; unsupported engines/locales are optional.
        return unavailable
