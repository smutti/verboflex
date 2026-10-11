"""Write the canonical OpenAPI document to stdout or atomically to a file."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from verboflex.main import app


def main(output: Path | None = None) -> None:
    """Serialize the live application contract deterministically."""
    document = (
        json.dumps(
            app.openapi(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    if output is None:
        sys.stdout.write(document)
        return
    # Readers must see either the previous complete schema or the new one,
    # including when an export fails or runs alongside backend contract tests.
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(document, encoding="utf-8")
        temporary.chmod(0o644)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    main(parser.parse_args().output)
