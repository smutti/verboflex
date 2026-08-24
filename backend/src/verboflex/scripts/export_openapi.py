"""Write the canonical FastAPI OpenAPI document to standard output."""

import json
import sys

from verboflex.main import app


def main() -> None:
    """Serialize the live application contract deterministically."""
    json.dump(
        app.openapi(),
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
