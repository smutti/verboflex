"""Synthetic renderer boundary for application E2E, never an Android renderer."""

import argparse
import json
import struct
import zlib
from pathlib import Path


def chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.input.read_bytes())
    assert bundle["capture"]["runner_profile"] == "synthetic-e2e"
    assert bundle["code_commit"] == "1" * 40
    assert bundle["translations_commit"] == "1" * 40
    assert bundle["request"]["preview_function"] == "demo.ScreenPreview"
    title = next(
        v["text"]
        for v in bundle["values"]
        if v["key"] == "title" and v["language"] == "it"
    )
    assert title in {"Synthetic imported title", "Saved on demand"}
    args.output.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"SyntheticTitle\0" + title.encode("ascii"))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x30\x80\xc0" * 2) * 2))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    main()
