#!/usr/bin/env python3
"""Fail-closed proof for the two exact Phase 1 SQLAlchemy join equivalents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXPECTED_RECORDS = (
    (
        "verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18",
        "join(User, None)",
        (
            "SQLAlchemy 2.0.52 infers the AuthSession.user_id foreign-key join and "
            "compiles byte-identical PostgreSQL SQL."
        ),
    ),
    (
        "verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_20",
        "join(User)",
        (
            "SQLAlchemy 2.0.52 infers the AuthSession.user_id foreign-key join and "
            "compiles byte-identical PostgreSQL SQL."
        ),
    ),
)


def load_mapping(path: Path) -> tuple[tuple[str, str, str], ...]:
    """Load the source-bound mapping without accepting duplicate or broad rows."""
    records: list[tuple[str, str, str]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = tuple(field.strip() for field in line.split("|"))
        if len(fields) != 3 or any(not field for field in fields):
            raise ValueError(f"invalid equivalent mutant row at line {line_number}")
        name, variant, rationale = fields
        records.append((name, variant, rationale))
    if len({record[0] for record in records}) != len(records):
        raise ValueError("duplicate equivalent mutant name")
    return tuple(records)


def compiled_sql(backend_root: Path) -> tuple[str, str, str, str]:
    """Compile explicit, equivalent, and deliberately divergent join statements."""
    sys.path.insert(0, str(backend_root / "src"))
    from sqlalchemy import select, true
    from sqlalchemy.dialects import postgresql
    from verboflex.models.auth_session import AuthSession
    from verboflex.models.user import User

    dialect = postgresql.dialect()

    def compile_statement(statement: object) -> str:
        return str(statement.compile(dialect=dialect))  # type: ignore[attr-defined]

    explicit = compile_statement(
        select(AuthSession.user_id).join(User, User.id == AuthSession.user_id)
    )
    explicit_none = compile_statement(select(AuthSession.user_id).join(User, None))
    inferred = compile_statement(select(AuthSession.user_id).join(User))
    divergent = compile_statement(select(AuthSession.user_id).join(User, true()))
    return explicit, explicit_none, inferred, divergent


def prove_equivalence(backend_root: Path, *, run_negative_control: bool) -> None:
    """Require identical production SQL and a known-divergent negative control."""
    explicit, explicit_none, inferred, divergent = compiled_sql(backend_root)
    if explicit != explicit_none or explicit != inferred:
        raise ValueError("documented equivalent joins no longer compile identical SQL")
    expected_join = "JOIN users ON users.id = auth_sessions.user_id"
    if explicit.count(expected_join) != 1:
        raise ValueError(
            "equivalent join proof did not compile the exact ownership predicate"
        )
    if run_negative_control:
        if explicit == divergent or "JOIN users ON true" not in divergent:
            raise ValueError("equivalent SQL negative control did not diverge")
        print("equivalent SQL proof negative control: PASS")
    print("equivalent SQL proof: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        records = load_mapping(args.mapping)
        if records != EXPECTED_RECORDS:
            raise ValueError(
                "equivalent mutant mapping drifted outside the exact approved set"
            )
        if not args.backend_root.joinpath(
            "src/verboflex/models/auth_session.py"
        ).is_file():
            raise ValueError(
                "backend root does not contain the source-bound AuthSession model"
            )
        prove_equivalence(args.backend_root, run_negative_control=args.self_test)
    except (OSError, ValueError) as error:
        print(f"equivalent mutant proof error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
