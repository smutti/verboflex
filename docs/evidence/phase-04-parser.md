# Phase 04 Parser Checkpoint Evidence

This ledger contains only fixed commands, tool versions, counts, durations, return codes, manifest hashes, and redacted output digests. It contains no localization source, provider payload, credential, environment value, or diagnostic body.

## Verdict

- Gate-status: PASS
- Persistence-authority: NOT STARTED
- Flagged-package-installation: ABSENT
- Parser-test-count: 169
- Approved-third-party-license-count: 106
- Worker-ping-responses: 1
- Backend-value-count: 1
- Worker-value-count: 1
- Backend-canonical-digest: 25d055f0dd29b18838e781d614c1ac318ac416e783d044b42acb538000d91213
- Worker-canonical-digest: 25d055f0dd29b18838e781d614c1ac318ac416e783d044b42acb538000d91213
- Runtime-image-digest: 9879fedfc9e05a6637a9b7eb1b7f8dabd44737d585ba2e9ca40fe4d201c5fe89
- Persistence-writes: 0
- Secret-scan: PASS
- Source-body-scan: PASS
- Cleanup: PASS

## Tool Versions

- uv: 0.11.12
- Python: 3.14.7
- pytest: 9.1.1
- pytest-cov: 7.1.0
- Ruff: 0.16.4
- mypy: 2.3.1
- pip-audit: 2.10.1
- pip-licenses: 5.5.5
- Docker Engine: 29.7.2
- Docker Compose: 5.3.1

## Command Records

| Check | Command | Duration (ms) | Return code | Count | Redacted output SHA-256 |
|---|---|---:|---:|---:|---|
| Parser package branch coverage | `uv run --project backend pytest backend/tests/unit/localization/importing --cov=verboflex.localization.importing --cov-branch --cov-report=term-missing --cov-fail-under=100 -q` | 6264 | 0 | 169 | `ecc8a0bb7346fdae11d9d06d9e3f0e447717d3b200eb578f688bfd2041aba35d` |
| Parser Ruff format | `uv run --project backend ruff format --check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing` | 41 | 0 | - | `04eb0d6e6734823dcd2b2b704729e976f683df7a8f334da7216520ef1cb319bf` |
| Parser Ruff lint | `uv run --project backend ruff check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing` | 41 | 0 | - | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| Parser mypy | `uv run --project backend mypy backend/src/verboflex/localization/importing` | 210 | 0 | - | `050c52a2b0c61e8b681ef5c485e0bc03340b8d55148e0acef27d744c8be42033` |
| Python dependency audit | `uv run --project backend pip-audit` | 968 | 0 | - | `f82c381625d03c68ddf9f598904e5ebbb4931236a5160cefcf1633a1e4b26eed` |
| Python license inventory | `uv run --project backend pip-licenses --format=json --with-urls` | 305 | 0 | 107 | `3d9ac5c1e18e901b2fa94db7ea42cdd15cf4788f0b435a2cce780492d7d67b9e` |
| Repository Python license policy | `bash tools/phase4_parser_checkpoint.sh --license-policy [owner-only inventory]` | 38 | 0 | 106 | `c05e837678ccd3f4d942d7fa5f152c62f88b31c3320c2d706dc292913e4577e7` |
| Flagged package absence | `repository manifests exclude regex==2026.9.3 and @tanstack/react-virtual==3.14.10` | 36 | 0 | - | `f666816ecaa97d1b1b76d577d2b268f357febc64b8301f182164869b98f69282` |
| Conformance manifest equality | `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py::test_fixture_manifest_category_equality -q` | 454 | 0 | - | `016a4093788648644b08006f7d1d171ca7639313677f5aa929f004d4a3e52465` |
| Backend and worker parser container smoke | `bash tools/phase4_parser_checkpoint.sh --container-smoke` | 28882 | 0 | 1 | `2d5b2d24663da39f7fdd01b4a0b4a122ca9e1a01d223fc6ec46ebfd98f0e13bb` |

## Fixture Manifest Hashes

| Manifest | SHA-256 |
|---|---|
| `backend/tests/fixtures/localization/android/manifest.json` | `f35f15cc6dc35f11fe7d5dbfaa50c942e8be64f4bb55eb7ee25159153a11f80d` |
| `backend/tests/fixtures/localization/conformance/manifest.json` | `153cb1e98446edcf9fdc82ae0c956c07fd019492a7caaac2f646aea53992613c` |
| `backend/tests/fixtures/localization/ios/manifest.json` | `18e74be0e952e82ab78534365d9f7b85898caf769678aeb4b6b30b3fd90f1681` |
| `backend/tests/fixtures/localization/json/manifest.json` | `5750e6aa122d15ec680bf6159f460f1cde195bcb44687f06a385614fe5225ff2` |
| `backend/tests/fixtures/localization/qt/manifest.json` | `1682978e4df14f1915419ce3d9c2e16df7f8a96578eacdefda2e5c462dc2cb43` |

## Boundary Proof

- The complete four-format parser package passed with the configured 100% statement and branch threshold.
- The exact supported/rejected category manifests passed the named equality test.
- Dependency vulnerability and repository license policy checks passed before either flagged dependency was installed.
- A unique disposable Compose stack returned one Celery ping response and byte-equal, nonempty backend/worker canonical digests.
- The container parser probes ran with SQLAlchemy persistence methods fail-closed and reported zero persistence writes.
- Runtime logs and result records passed seeded-secret, credential-shape, and source-body scans before complete cleanup.
