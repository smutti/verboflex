"""Deterministic Phase 2 multi-source semantic closure audit."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_phase2_spec_edge_traceability import (
    _assert_nodes_collect,
    _assert_source_matrix_equal,
    _load_matrix,
    _normalize,
)
from yaml.resolver import BaseResolver

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE_DIR = REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration"
ROADMAP_PATH = REPOSITORY_ROOT / ".planning" / "ROADMAP.md"
REQUIREMENTS_PATH = REPOSITORY_ROOT / ".planning" / "REQUIREMENTS.md"
CONTEXT_PATH = PHASE_DIR / "02-CONTEXT.md"
RESEARCH_PATH = PHASE_DIR / "02-RESEARCH.md"
SPEC_PATH = PHASE_DIR / "02-SPEC.md"
UI_SPEC_PATH = PHASE_DIR / "02-UI-SPEC.md"
COVERAGE_PATH = PHASE_DIR / "COVERAGE.md"
REVIEW_PATH = PHASE_DIR / "02-REVIEW.md"
VERIFICATION_PATH = PHASE_DIR / "02-VERIFICATION.md"
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src" / "verboflex"
FRONTEND_SOURCE = REPOSITORY_ROOT / "frontend" / "src"
FRONTEND_E2E = REPOSITORY_ROOT / "frontend" / "e2e" / "admin-configuration.spec.ts"
BASE_COMPOSE = REPOSITORY_ROOT / "docker-compose.yml"
SMOKE_HARNESS = REPOSITORY_ROOT / "tools" / "phase2_smoke.sh"

GOAL_FINGERPRINT = "46b6d274b4cc0980cbad"
REQUIREMENT_FINGERPRINTS = {
    "AUTH-02": "d3b6dde2a0a949e7b257",
    "AUTH-03": "b78e631b96f01916ce2b",
    "PROD-01": "ac911987fd02fb25c295",
    "PROD-02": "9a0579cbd10f55da6026",
    "PROD-03": "75af7b224273195ba984",
    "PROD-04": "9797b9dc8d519a0171a5",
    "PROD-05": "c78bf3cbee639a13e06d",
    "PROD-06": "344539952d4a49f9a315",
    "PROD-07": "76e5d8488fd4b4bdfa0e",
    "PROD-08": "fa5ee077123693fa5326",
    "PROD-09": "9b63321cc4ef6c9a81a8",
    "BITB-01": "d699a7d666ad422f76e9",
    "BITB-03": "7536422af24199c14f93",
    "BITB-04": "8005998a9d6b8ef42117",
    "UI-03": "80fbae32336a3dae0699",
}
DECISION_FINGERPRINTS = {
    "D-01": "c02d0ece938b11a2c8f2",
    "D-02": "d0250d5349f744c8c1d8",
    "D-03": "ca05a0da336d4efe39d1",
    "D-04": "2533f3934b94fae86976",
    "D-05": "da3dfaa412b6a2bbd079",
    "D-06": "e9d64fa6ac2a58923b1e",
    "D-07": "f1b72e1c4da03906df0a",
    "D-08": "93fc42cfe0a2a930ef04",
    "D-09": "35aea318c82d1e969dc4",
    "D-10": "91514ce3f40ff03239b2",
    "D-11": "e68553ee16b3fa930e96",
    "D-12": "2ed1bff2bd0db6b79bdf",
    "D-13": "9e90e55ec03343b2a9a3",
    "D-14": "8808557a9f9d10dad20e",
    "D-15": "6b22ff403f083697e5da",
    "D-16": "fbb69e9726e6a2e27704",
    "D-17": "b8b69aab6f99efa07bbf",
    "D-18": "dad12a4f5c30a3b7a472",
    "D-19": "9e28611d1bb805082519",
    "D-20": "f652689e8408eb9aa893",
    "D-21": "5ae12c59efabd4dc6198",
    "D-22": "a2f73c024d28f90c5502",
    "D-23": "5c7eb766412071140752",
}
ASSUMPTION_FINGERPRINTS = {
    "A-01": "a67c963579492d95660d",
    "A-02": "dca64f2dfbf163cfc156",
    "A-03": "d4a1ec3b3ae25420d767",
}
PROHIBITION_FINGERPRINTS = {
    "P-01": "1c36940fe816794e63d9",
    "P-02": "40fa166d23abafe15a29",
    "P-03": "3a0f57b15edd94582224",
    "P-04": "b6562b02ccfdeed4116e",
    "P-05": "3debe14aacf5d56474c8",
    "P-06": "407e3df8bd6d2a3ced1c",
    "P-07": "1e4cf8c23eb1de66adcb",
    "P-08": "e8328d4671f73cb62afd",
    "P-09": "319428b10514cb23bb09",
}
UI_FINGERPRINTS = {
    "empty": "26933cedbe75742f27cc",
    "loading": "c39332490004f5436bc7",
    "error": "c8f0c3b3e0b1643f5f49",
    "populated": "dcf595280163157c1efe",
    "partial": "cb5911ca1df274e3acbb",
    "overflow": "e5ab2bbfe93f7cee748d",
    "zero-one-many": "9f46932e0eba703925c2",
    "long-text": "08549ee968721bd5ed52",
}
REVIEW_INVENTORY_KEYS = {
    *(f"CR-{number:02d}" for number in range(1, 16)),
    *(f"WR-{number:02d}" for number in range(1, 9)),
}
OPEN_WARNING_KEYS = {f"WR-{number:02d}" for number in range(3, 9)}
VERIFIER_INVENTORY_TOTALS = {
    "phase_goal": 1,
    "roadmap_success_criteria": 8,
    "requirements": 15,
    "context_decisions": 23,
    "research_assumptions": 3,
    "spec_edge_rows": 54,
    "prohibitions": 9,
    "ui_considerations": 8,
    "bitbucket_capabilities": 44,
    "review_rows": 23,
}
CAPABILITY_FINGERPRINTS = {
    "oauth-client-credentials-acquisition": "ed66d7cd97cac016e9d7",
    "oauth-client-credentials-reacquisition": "42259ff2f9a9b5724143",
    "oauth-authorization-code-callback-and-refresh-token-flows": "cbc2005f58c1f8162c43",
    "oauth-effective-scope-inspection": "b2994bc97e5fa351744f",
    "repository-metadata-by-workspace-and-slug": "e556cc7307512a1f40f6",
    "branch-listing-with-provider-pagination": "32a68f5be02cc980b16b",
    "branch-to-commit-resolution": "70897320275a44f69129",
    "source-tree-directory-pagination": "60e4f2a103f56a2e7362",
    "raw-source-file-read-at-commit": "30979a48f286549aaaed",
    "provider-next-url-validation": "764563d68df0d66f6f67",
    "oauth-provider-side-token-revocation": "047fcb4b64ba6a7b5acb",
    "repository-listing-and-search": "915efe0605ba031ffe8b",
    "account-profile-and-email": "ebd5d1e7b67b82213f75",
    "workspace-membership-and-permissions": "0312ae5ff05f92e50940",
    "project-listing-and-metadata": "810a4f050dabb3193399",
    "workspace-and-project-administration": "c84214885380d2985473",
    "tag-listing-and-other-ref-discovery": "ad0c26d549cb4658d1c5",
    "commit-history-listing-and-search": "603a9fb6bd50048197b6",
    "commit-diff-diffstat-and-patch-read": "fad2efdd71c5ac776882",
    "commit-status-read-and-write": "84679dcc376c08913442",
    "source-file-create-update-delete": "a093a8257ca21c498a0e",
    "branch-create-update-delete": "f5da049e89d868671375",
    "tag-create-update-delete": "3773200e6a2963b6179e",
    "commit-create": "5c7cd884b2004241a5b1",
    "pull-request-list-and-read": "be9f88e0fbb43b00c397",
    "pull-request-create-and-update": "75d043c5aa3446164b97",
    "pull-request-merge-decline-and-approve": "7b6e82b8688e1144ea7b",
    "pull-request-comments-tasks-and-activity": "4288eee58a71a74e7136",
    "pull-request-diff-and-diffstat": "3c46142895290703c223",
    "repository-webhook-list-and-read": "fcb11ef5db456071526a",
    "repository-webhook-create-update-delete": "a22f43f389e1a8689332",
    "repository-settings-and-permissions-admin": "4f60d568c81e96099f9d",
    "branch-restrictions-and-merge-checks-admin": "2fea2bb53aaf95eb4449",
    "deploy-keys-access-keys-and-ssh-keys-admin": "9804a4136b0834c4653c",
    "pipelines-list-and-read": "602dd3fcbc42486f4673",
    "pipelines-run-stop-and-manage": "76c4b6c12e510a2ea862",
    "deployments-and-environments": "abe177c928c5d95b1944",
    "issues-list-and-read": "fc9d22cf816d89ed0aa4",
    "issues-create-update-delete-and-comments": "44c094f962763118199f",
    "downloads-list-and-read": "d84558bf2a189ea724de",
    "downloads-upload-and-delete": "2d21b157cd676d0575e8",
    "wiki-read-and-write": "7d23c8efc3baf21ddc0b",
    "snippets-read-and-write": "f57c539ec98cd3e287a6",
    "code-search": "58d15f3fcf114a8878c7",
}
DECLARED_CREDENTIAL_REWRITE = {
    "oauth-authorization-code-start": "oauth-client-credentials-acquisition",
    "oauth-authorization-code-exchange": "oauth-client-credentials-reacquisition",
    "oauth-refresh-token-exchange-and-rotation": (
        "oauth-authorization-code-callback-and-refresh-token-flows"
    ),
}

NODE_USER = (
    "backend/tests/integration/test_admin_user_concurrency.py::"
    "test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin"
)
NODE_REPOSITORY = (
    "backend/tests/integration/test_repository_registry.py::"
    "test_two_session_registration_race_has_one_201_one_409_and_one_row"
)
NODE_PRODUCT = (
    "backend/tests/integration/test_product_publication.py::"
    "test_product_lock_linearizes_publish_equal_retry_and_stale_writer"
)
NODE_OAUTH = (
    "backend/tests/integration/test_bitbucket_oauth.py::"
    "test_client_credentials_rotation_and_revoke_serialize"
)
NODE_PREVIEW = (
    "backend/tests/integration/test_preview_jobs.py::"
    "test_new_commit_makes_an_inflight_completion_stale_and_nonconfirmable"
)
NODE_SCOPE = (
    "backend/tests/architecture/test_phase2_scope.py::"
    "test_openapi_has_no_deferred_resource_or_provider_write_surface"
)
NODE_CAPABILITY = (
    "backend/tests/architecture/test_phase2_live_provider_smoke.py::"
    "test_coverage_rewrites_exactly_three_keys_without_semantic_loss"
)
NODE_WORKER = (
    "backend/tests/architecture/test_phase2_live_provider_smoke.py::"
    "test_worker_loss_smoke_proves_bounded_terminalization_and_retry"
)
NODE_GAUNTLET = (
    "backend/tests/architecture/test_phase2_live_provider_smoke.py::"
    "test_smoke_contract_scans_all_evidence_and_always_tears_down"
)
NODE_UI = (
    "frontend/src/features/admin/products/ProductConfiguration.test.tsx::"
    "keeps all five wizard steps reachable through persistent 320px keyboard and pointer controls"
)
NODE_PAGING = (
    "frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx::"
    "restores configured branch 101 exactly and pages one cursor per action"
)
NODE_WORKSPACE = (
    "frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx::"
    "loads exactly three bounded administrator summaries from server authority"
)

GAP_RUNTIME_BINDINGS = {
    "CR-01": {
        "runtime": ("compose:x-backend-common.environment.VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID"),
        "evidence": (
            "backend/tests/architecture/test_phase2_live_provider_smoke.py::"
            "test_base_compose_inherits_exact_provider_settings_without_secret_output"
        ),
    },
    "CR-02": {
        "runtime": (
            "python:verboflex.services.bitbucket_oauth:"
            "BitbucketOAuthService.acquire_client_credentials"
        ),
        "evidence": (
            "backend/tests/integration/test_bitbucket_oauth.py::"
            "test_client_credentials_provider_exchange_is_exact_and_bounded"
        ),
    },
    "CR-03": {
        "runtime": "openapi:connect_admin_bitbucket_oauth",
        "evidence": (
            "backend/tests/integration/test_bitbucket_oauth.py::"
            "test_client_credentials_service_has_no_callback_or_refresh_authority"
        ),
    },
    "CR-04": {
        "runtime": (
            "python:verboflex.services.bitbucket_oauth:"
            "BitbucketOAuthService.acquire_repository_read_lease"
        ),
        "evidence": (
            "backend/tests/integration/test_bitbucket_oauth.py::"
            "test_client_credentials_expiry_boundary_is_authoritative"
        ),
    },
    "CR-05": {
        "runtime": "python:verboflex.services.products:_clone_active_revision_graph",
        "evidence": (
            "backend/tests/api/test_admin_products.py::"
            "test_existing_product_edit_clones_complete_graph_once_and_isolates_candidate_identity"
        ),
    },
    "CR-06": {
        "runtime": "python:verboflex.services.publication:reactivate_product",
        "evidence": (
            "e2e:unchanged active revision reactivation uses real backend state and "
            "blocks stale confirmation"
        ),
    },
    "CR-07": {
        "runtime": (
            "typescript:frontend/src/features/admin/products/"
            "ProductWizardPage.tsx:mobileWizardNavigation"
        ),
        "evidence": "e2e:mobile five-step wizard remains reachable at 320 pixels",
    },
    "CR-08": {
        "runtime": (
            "typescript:frontend/src/features/admin/useCursorCollection.ts:useCursorCollection"
        ),
        "evidence": (
            "e2e:51st mapping preview readiness consumes terminal cursor before lifecycle authority"
        ),
    },
    "CR-09": {
        "runtime": ("python:verboflex.services.preview_jobs:reconcile_stale_preview_jobs"),
        "evidence": (
            "backend/tests/integration/test_preview_jobs.py::"
            "test_retry_after_watchdog_timeout_isolated_from_old_worker_completion"
        ),
    },
    "CR-10": {
        "runtime": (
            "python:verboflex.services.admin_users:_deactivate_user_under_admin_authority_lock"
        ),
        "evidence": (
            "backend/tests/test_cli.py::"
            "test_cli_sole_admin_deactivation_fails_without_changing_authority"
        ),
    },
    "WR-01": {
        "runtime": (
            "typescript:frontend/src/features/workspace/"
            "WorkspaceOverviewPage.tsx:WorkspaceOverviewPage"
        ),
        "evidence": (
            "e2e:role-aware Workspace navigation stays location-authoritative on desktop and mobile"
        ),
    },
    "WR-02": {
        "runtime": ("migration:backend/alembic/versions/0009_product_graph_integrity.py:upgrade"),
        "evidence": (
            "backend/tests/integration/test_migrations.py::"
            "test_product_graph_integrity_upgrade_downgrade_and_reupgrade"
        ),
    },
    "G1": {
        "runtime": (
            "python:verboflex.services.admin_users:_deactivate_user_under_admin_authority_lock"
        ),
        "evidence": (
            "backend/tests/integration/test_admin_user_concurrency.py::"
            "test_cross_entry_cli_and_http_deactivation_preserve_one_active_admin_and_both_uuids"
        ),
    },
    "G2": {
        "runtime": "python:verboflex.services.products:_clone_active_revision_graph",
        "evidence": (
            "backend/tests/integration/test_product_publication.py::"
            "test_product_lock_linearizes_publish_equal_retry_and_stale_writer"
        ),
    },
    "G3": {
        "runtime": ("compose:x-backend-common.environment.VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET"),
        "evidence": "smoke:--mock-live-provider",
    },
    "G4": {
        "runtime": (
            "typescript:frontend/src/features/admin/products/"
            "ProductWizardPage.tsx:ProductWizardPage"
        ),
        "evidence": "e2e:mobile five-step wizard remains reachable at 320 pixels",
    },
    "G5": {
        "runtime": ("python:verboflex.services.preview_jobs:reconcile_stale_preview_jobs"),
        "evidence": "smoke:--worker-loss",
    },
}

EXPECTED_GAP_RUNTIME_KEYS = {
    *(f"CR-{number:02d}" for number in range(1, 11)),
    "WR-01",
    "WR-02",
    *(f"G{number}" for number in range(1, 6)),
}


def _fingerprint(value: str) -> str:
    return hashlib.sha256(_normalize(value).encode()).hexdigest()[:20]


def _unique(rows: list[tuple[str, Any]], *, source: str) -> dict[str, Any]:
    counts = Counter(key for key, _ in rows)
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    assert not duplicates, f"{source} contains duplicate semantic keys: {duplicates}"
    return dict(rows)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        assert key not in mapping, f"frontmatter contains duplicate key: {key}"
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_bounded_frontmatter(text: str, *, source: str) -> dict[str, Any]:
    match = re.match(r"\A---\r?\n(?P<yaml>.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    assert match, f"{source} has no canonical YAML frontmatter"
    payload = match.group("yaml")
    assert len(payload.encode("utf-8")) <= 256 * 1024, f"{source} frontmatter is unbounded"
    loaded = yaml.load(payload, Loader=_UniqueKeySafeLoader)
    assert isinstance(loaded, dict), f"{source} frontmatter is not a mapping"
    return loaded


def _goal() -> dict[str, str]:
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    match = re.search(r"### Phase 2:.*?\n\n\*\*Goal\*\*: (.*?)\n", roadmap, re.S)
    assert match, "Phase 2 goal is absent"
    return {"GOAL": _fingerprint(match.group(1))}


def _requirements() -> dict[str, str]:
    text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    rows = [
        (match.group("key"), _fingerprint(match.group("meaning")))
        for match in re.finditer(
            r"^- \[[ x]\] \*\*(?P<key>[A-Z]+-\d{2})\*\*: (?P<meaning>.*)$",
            text,
            re.M,
        )
        if match.group("key") in REQUIREMENT_FINGERPRINTS
    ]
    return _unique(rows, source="requirements")


def _decisions() -> dict[str, str]:
    text = CONTEXT_PATH.read_text(encoding="utf-8")
    rows = [
        (match.group("key"), _fingerprint(match.group("meaning")))
        for match in re.finditer(r"^- \*\*(?P<key>D-\d{2}):\*\* (?P<meaning>.*)$", text, re.M)
    ]
    return _unique(rows, source="decisions")


def _assumptions() -> dict[str, str]:
    text = RESEARCH_PATH.read_text(encoding="utf-8")
    rows: list[tuple[str, str]] = []
    for number in range(1, 4):
        key = f"A-{number:02d}"
        match = re.search(rf"^### {key} .*?\n.*?(?=^### A-0[1-3] |^## )", text, re.M | re.S)
        assert match, f"research assumption {key} is absent"
        rows.append((key, _fingerprint(match.group(0))))
    return _unique(rows, source="assumptions")


def _table_rows(text: str, *, start: str, end: str) -> list[list[str]]:
    section = text.split(start, 1)[1].split(end, 1)[0]
    rows: list[list[str]] = []
    for line in section.splitlines():
        if line.startswith("|"):
            rows.append([_normalize(cell).strip("`") for cell in line.strip("|").split("|")])
    return rows


def _prohibitions() -> dict[str, str]:
    rows = [
        row
        for row in _table_rows(
            SPEC_PATH.read_text(encoding="utf-8"),
            start="## Prohibitions (must-NOT)",
            end="## Ambiguity Report",
        )
        if row and row[0].startswith("MUST NOT")
    ]
    return {f"P-{number:02d}": _fingerprint(" | ".join(row)) for number, row in enumerate(rows, 1)}


def _ui_considerations() -> dict[str, str]:
    keys = EXPECTED_KEYS["ui"]
    rows = [
        row
        for row in _table_rows(
            UI_SPEC_PATH.read_text(encoding="utf-8"),
            start="## UI Considerations",
            end="### Open-axis considerations",
        )
        if row and row[0] in keys
    ]
    return _unique(
        [(row[0], _fingerprint(" | ".join(row))) for row in rows],
        source="UI considerations",
    )


def _capabilities() -> dict[str, dict[str, str]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for line in COVERAGE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [_normalize(cell).strip("`") for cell in line.strip("|").split("|")]
        if len(cells) == 3 and cells[1] in {"INTEGRATE", "OPT-OUT"}:
            rows.append(
                (
                    cells[0],
                    {
                        "fingerprint": _fingerprint(" | ".join(cells)),
                        "decision": cells[1],
                        "reason": cells[2],
                    },
                )
            )
    return _unique(rows, source="capabilities")


def _current_review_table(text: str) -> dict[str, dict[str, str]]:
    marker = "### Current CR/WR Inventory Re-audit"
    assert marker in text, "current review inventory table is absent"
    section = text.split(marker, 1)[1]
    next_heading = re.search(r"^### ", section, re.M)
    if next_heading:
        section = section[: next_heading.start()]
    rows = [
        row
        for line in section.splitlines()
        if line.startswith("|")
        for row in [[_normalize(cell).strip("`") for cell in line.strip("|").split("|")]]
        if row and re.fullmatch(r"(?:CR|WR)-\d{2}", row[0])
    ]
    return _unique(
        [
            (
                row[0],
                {
                    "disposition": (
                        "open" if re.match(r"^\*\*OPEN\b|^OPEN\b", row[1], re.I) else "closed"
                    ),
                    "severity": "critical" if row[0].startswith("CR-") else "warning",
                },
            )
            for row in rows
        ],
        source="current review table",
    )


def _review_findings(text: str | None = None) -> dict[str, Any]:
    document = REVIEW_PATH.read_text(encoding="utf-8") if text is None else text
    frontmatter = _load_bounded_frontmatter(document, source="review")
    status = frontmatter.get("status")
    assert status in {"clean", "issues_found"}, "unsupported reviewer status"

    findings = frontmatter.get("findings")
    assert isinstance(findings, dict), "review findings are absent"
    assert set(findings) == {"critical", "warning", "info", "total"}, (
        "review finding-count keys drifted"
    )
    assert all(type(findings[key]) is int and findings[key] >= 0 for key in findings), (
        "review finding counts must be non-negative integers"
    )
    assert findings["total"] == findings["critical"] + findings["warning"] + findings["info"]

    inventory = frontmatter.get("review_inventory")
    assert isinstance(inventory, dict), "structured review inventory is absent"
    assert set(inventory) == REVIEW_INVENTORY_KEYS, "structured review inventory key drift"
    normalized_inventory: dict[str, dict[str, str]] = {}
    for key, raw_record in inventory.items():
        assert isinstance(key, str) and isinstance(raw_record, dict), (
            "review inventory record is malformed"
        )
        assert set(raw_record) == {"disposition", "severity"}, (
            f"review inventory record shape drifted: {key}"
        )
        disposition = raw_record["disposition"]
        severity = raw_record["severity"]
        assert disposition in {"closed", "open"}, f"unsupported review disposition: {key}"
        expected_severity = "critical" if key.startswith("CR-") else "warning"
        assert severity == expected_severity, f"review severity drifted: {key}"
        normalized_inventory[key] = {
            "disposition": disposition,
            "severity": severity,
        }

    table_inventory = _current_review_table(document)
    assert table_inventory == normalized_inventory, (
        "structured review inventory disagrees with the authoritative current table"
    )
    open_critical = {
        key
        for key, record in normalized_inventory.items()
        if record == {"disposition": "open", "severity": "critical"}
    }
    open_warning = {
        key
        for key, record in normalized_inventory.items()
        if record == {"disposition": "open", "severity": "warning"}
    }
    assert open_critical in ({"CR-14", "CR-15"}, set()), "review blocker transition is unsupported"
    assert open_warning == OPEN_WARNING_KEYS, "retained review warnings drifted"
    assert findings["critical"] == len(open_critical)
    assert findings["warning"] == len(open_warning)
    assert findings["info"] == 0
    expected_status = "clean" if findings["total"] == 0 else "issues_found"
    assert status == expected_status, "review status disagrees with finding counts"
    return {
        "findings": dict(findings),
        "inventory": normalized_inventory,
        "status": status,
    }


def _verifier_groups(text: str | None = None) -> dict[str, Any]:
    document = VERIFICATION_PATH.read_text(encoding="utf-8") if text is None else text
    frontmatter = _load_bounded_frontmatter(document, source="verifier")
    status = frontmatter.get("status")
    assert status in {"passed", "gaps_found", "human_needed"}, "unsupported verifier status"

    inventories = frontmatter.get("inventories")
    assert isinstance(inventories, dict), "verifier inventories are absent"
    assert set(inventories) == set(VERIFIER_INVENTORY_TOTALS), (
        "verifier inventory identifiers drifted"
    )
    normalized_inventories: dict[str, dict[str, int]] = {}
    for key, total in VERIFIER_INVENTORY_TOTALS.items():
        raw_record = inventories[key]
        assert isinstance(raw_record, dict) and set(raw_record) == {"count", "total"}, (
            f"verifier inventory record shape drifted: {key}"
        )
        count = raw_record["count"]
        declared_total = raw_record["total"]
        assert type(count) is int and type(declared_total) is int
        assert declared_total == total and 0 <= count <= declared_total, (
            f"verifier inventory count drifted: {key}"
        )
        normalized_inventories[key] = {"count": count, "total": declared_total}

    review = frontmatter.get("review")
    assert isinstance(review, dict), "verifier review summary is absent"
    assert set(review) == {
        "status",
        "critical",
        "warning",
        "info",
        "open_blockers",
        "open_warnings",
    }, "verifier review summary shape drifted"
    assert review["status"] in {"clean", "issues_found"}
    assert all(
        type(review[key]) is int and review[key] >= 0 for key in ("critical", "warning", "info")
    )
    assert isinstance(review["open_blockers"], list)
    assert isinstance(review["open_warnings"], list)
    assert len(review["open_blockers"]) == len(set(review["open_blockers"]))
    assert len(review["open_warnings"]) == len(set(review["open_warnings"]))
    assert set(review["open_blockers"]) in ({"CR-14", "CR-15"}, set())
    assert set(review["open_warnings"]) == OPEN_WARNING_KEYS
    assert review["critical"] == len(review["open_blockers"])
    assert review["warning"] == len(review["open_warnings"])
    assert review["info"] == 0
    assert review["status"] == (
        "clean" if review["critical"] + review["warning"] + review["info"] == 0 else "issues_found"
    )

    gaps = frontmatter.get("gaps")
    assert isinstance(gaps, list), "verifier gaps must be a collection"
    for gap in gaps:
        assert isinstance(gap, dict), "verifier gap record is malformed"
        assert {"truth", "status", "reason"}.issubset(gap), "verifier gap record is incomplete"
        assert isinstance(gap["truth"], str) and gap["truth"].strip()
        assert gap["status"] in {"failed", "partial"}
        assert isinstance(gap["reason"], str) and gap["reason"].strip()

    if status == "passed":
        assert not gaps, "passed verifier retains gaps"
        assert all(
            record["count"] == record["total"] for record in normalized_inventories.values()
        ), "passed verifier has incomplete inventories"
        assert review["critical"] == 0 and not review["open_blockers"], (
            "passed verifier retains blockers"
        )
    elif status == "gaps_found":
        assert gaps, "gaps_found verifier has no concrete gaps"

    return {
        "gaps": gaps,
        "inventories": normalized_inventories,
        "review": dict(review),
        "status": status,
    }


def _closing(plan: str, task: int, node: str) -> dict[str, object]:
    return {"plan_task": f"{plan}/T{task}", "node": node}


def _closure(source: str, key: str, value: object) -> dict[str, object]:
    if source == "goal":
        return _closing("02-37", 2, NODE_GAUNTLET)
    if source == "requirements":
        routing = {
            "AUTH-02": ("02-23", 1, NODE_USER),
            "AUTH-03": ("02-23", 2, NODE_USER),
            "PROD-01": ("02-25", 1, NODE_PRODUCT),
            "PROD-02": ("02-24", 1, NODE_REPOSITORY),
            "PROD-03": ("02-24", 2, NODE_REPOSITORY),
            "PROD-04": ("02-24", 2, NODE_REPOSITORY),
            "PROD-05": ("02-25", 2, NODE_PRODUCT),
            "PROD-06": ("02-24", 2, NODE_REPOSITORY),
            "PROD-07": ("02-24", 2, NODE_REPOSITORY),
            "PROD-08": ("02-29", 2, NODE_PREVIEW),
            "PROD-09": ("02-25", 2, NODE_PREVIEW),
            "BITB-01": ("02-35", 2, NODE_OAUTH),
            "BITB-03": ("02-28", 1, NODE_PAGING),
            "BITB-04": ("02-21", 2, NODE_OAUTH),
            "UI-03": ("02-27", 1, NODE_UI),
        }
        return _closing(*routing[key])
    if source == "decisions":
        number = int(key.split("-")[1])
        if number <= 6:
            return _closing("02-23", 2, NODE_USER)
        if number <= 11:
            return _closing("02-24", 2, NODE_REPOSITORY)
        if number <= 18:
            return _closing("02-25", 2, NODE_PREVIEW)
        if number <= 20:
            return _closing("02-27", 1, NODE_UI)
        return _closing("02-35", 2, NODE_CAPABILITY)
    if source == "assumptions":
        return {
            "A-01": _closing("02-24", 1, NODE_PRODUCT),
            "A-02": _closing("02-25", 2, NODE_PREVIEW),
            "A-03": _closing("02-29", 2, NODE_WORKER),
        }[key]
    if source == "edges":
        assert isinstance(value, dict)
        requirement = key.split("-", 1)[0]
        plan = {
            "R1": "02-23",
            "R2": "02-23",
            "R3": "02-23",
            "R4": "02-25",
            "R5": "02-21",
            "R6": "02-24",
            "R7": "02-28",
            "R8": "02-25",
            "R9": "02-29",
            "R10": "02-25",
            "R11": "02-27",
            "R12": "02-29",
        }[requirement]
        return _closing(plan, 2, value["test_nodes"][0])
    if source == "prohibitions":
        return {
            "P-01": _closing("02-23", 2, NODE_USER),
            "P-02": _closing("02-25", 2, NODE_PRODUCT),
            "P-03": _closing("02-21", 2, NODE_OAUTH),
            "P-04": _closing("02-24", 2, NODE_REPOSITORY),
            "P-05": _closing("02-25", 2, NODE_PREVIEW),
            "P-06": _closing("02-25", 2, NODE_PRODUCT),
            "P-07": _closing("02-27", 1, NODE_UI),
            "P-08": _closing("02-25", 2, NODE_PRODUCT),
            "P-09": _closing("02-29", 2, NODE_SCOPE),
        }[key]
    if source == "ui":
        if key in {"overflow", "zero-one-many", "long-text"}:
            return _closing("02-34", 2, NODE_WORKSPACE)
        if key == "partial":
            return _closing("02-31", 2, NODE_PAGING)
        return _closing("02-27", 1, NODE_UI)
    if source == "capabilities":
        return _closing("02-35", 2, NODE_CAPABILITY)
    raise AssertionError(f"unsupported coverage source: {source}")


def _entry(source: str, key: str, semantic: object) -> dict[str, object]:
    return {"semantic": semantic, "closure": _closure(source, key, semantic)}


EXPECTED_KEYS = {
    "goal": {"GOAL"},
    "requirements": {
        "AUTH-02",
        "AUTH-03",
        "PROD-01",
        "PROD-02",
        "PROD-03",
        "PROD-04",
        "PROD-05",
        "PROD-06",
        "PROD-07",
        "PROD-08",
        "PROD-09",
        "BITB-01",
        "BITB-03",
        "BITB-04",
        "UI-03",
    },
    "decisions": {f"D-{number:02d}" for number in range(1, 24)},
    "assumptions": {"A-01", "A-02", "A-03"},
    "edges": {
        f"R{requirement}-{category}"
        for requirement, categories in {
            1: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            2: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            3: ("idempotency", "concurrency"),
            4: ("empty", "encoding", "idempotency", "concurrency"),
            5: ("idempotency", "concurrency"),
            6: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            7: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            8: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            9: ("adjacency", "empty", "encoding", "ordering", "idempotency", "concurrency"),
            10: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            11: ("adjacency", "empty", "ordering", "idempotency", "concurrency"),
            12: ("idempotency", "concurrency"),
        }.items()
        for category in categories
    },
    "prohibitions": {f"P-{number:02d}" for number in range(1, 10)},
    "ui": {
        "empty",
        "loading",
        "error",
        "populated",
        "partial",
        "overflow",
        "zero-one-many",
        "long-text",
    },
    "capabilities": set(CAPABILITY_FINGERPRINTS),
}


def _multi_source_inventory() -> dict[str, dict[str, object]]:
    edges = {row["edge_id"]: row for row in _load_matrix()}
    sources: dict[str, dict[str, object]] = {
        "goal": _goal(),
        "requirements": _requirements(),
        "decisions": _decisions(),
        "assumptions": _assumptions(),
        "edges": edges,
        "prohibitions": _prohibitions(),
        "ui": _ui_considerations(),
        "capabilities": _capabilities(),
    }
    return {
        source: {key: _entry(source, key, semantic) for key, semantic in source_inventory.items()}
        for source, source_inventory in sources.items()
    }


def _assert_shape(inventory: dict[str, dict[str, object]]) -> None:
    assert inventory.keys() == EXPECTED_KEYS.keys(), "canonical source group drift"
    for source, expected in EXPECTED_KEYS.items():
        assert inventory[source].keys() == expected, f"{source} semantic-key drift"


def _assert_semantics(inventory: dict[str, dict[str, object]]) -> None:
    expected_fingerprints = {
        "goal": {"GOAL": GOAL_FINGERPRINT},
        "requirements": REQUIREMENT_FINGERPRINTS,
        "decisions": DECISION_FINGERPRINTS,
        "assumptions": ASSUMPTION_FINGERPRINTS,
        "prohibitions": PROHIBITION_FINGERPRINTS,
        "ui": UI_FINGERPRINTS,
    }
    for source, expected in expected_fingerprints.items():
        actual = {key: entry["semantic"] for key, entry in inventory[source].items()}
        assert actual == expected, f"{source} meaning/status/reason drift"

    matrix = [entry["semantic"] for entry in inventory["edges"].values()]
    assert all(isinstance(row, dict) for row in matrix)
    _assert_source_matrix_equal(matrix)

    capabilities = inventory["capabilities"]
    actual_capability_fingerprints = {
        key: entry["semantic"]["fingerprint"] for key, entry in capabilities.items()
    }
    assert actual_capability_fingerprints == CAPABILITY_FINGERPRINTS


def _assert_capability_rewrite(inventory: dict[str, dict[str, object]]) -> None:
    capabilities = {key: entry["semantic"] for key, entry in inventory["capabilities"].items()}
    replacement_values = set(DECLARED_CREDENTIAL_REWRITE.values())
    identity_keys = set(capabilities) - replacement_values
    assert len(DECLARED_CREDENTIAL_REWRITE) == 3
    assert len(identity_keys) == 41
    assert set(DECLARED_CREDENTIAL_REWRITE).isdisjoint(capabilities)
    assert replacement_values.issubset(capabilities)
    assert {key: key for key in identity_keys}.keys() == identity_keys
    assert {key: capabilities[key]["decision"] for key in replacement_values} == {
        "oauth-client-credentials-acquisition": "INTEGRATE",
        "oauth-client-credentials-reacquisition": "INTEGRATE",
        "oauth-authorization-code-callback-and-refresh-token-flows": "OPT-OUT",
    }
    assert all(
        record["reason"] for record in capabilities.values() if record["decision"] == "OPT-OUT"
    )


def _assert_plan_task(plan_task: str) -> None:
    match = re.fullmatch(r"(?P<plan>02-\d{2})/T(?P<task>[1-9]\d*)", plan_task)
    assert match, f"invalid closing plan/task contract: {plan_task}"
    plan_path = PHASE_DIR / f"{match.group('plan')}-PLAN.md"
    assert plan_path.is_file(), f"closing plan is absent: {plan_path.name}"
    text = plan_path.read_text(encoding="utf-8")
    task_count = len(re.findall(r"<task(?:\s|>)", text))
    task_number = int(match.group("task"))
    assert task_number <= task_count, f"closing task does not exist: {plan_task}"
    assert re.search(rf"<name>Task {task_number}:", text), f"unnamed closing task: {plan_task}"


def _assert_reachability(inventory: dict[str, dict[str, object]]) -> None:
    nodes: set[str] = set()
    for source in inventory.values():
        for entry in source.values():
            closure = entry["closure"]
            assert isinstance(closure, dict)
            assert set(closure) == {"plan_task", "node"}
            _assert_plan_task(str(closure["plan_task"]))
            nodes.add(str(closure["node"]))
    _assert_nodes_collect([{"test_nodes": [node]} for node in sorted(nodes)])


def _all_requirement_ids() -> set[str]:
    return set(
        re.findall(
            r"^- \[[ x]\] \*\*([A-Z]+-\d{2})\*\*:",
            REQUIREMENTS_PATH.read_text(encoding="utf-8"),
            re.M,
        )
    )


def _assert_deferred_scope_rejected(inventory: dict[str, dict[str, object]]) -> None:
    admitted = set(inventory["requirements"])
    deferred_requirements = _all_requirement_ids() - set(REQUIREMENT_FINGERPRINTS)
    assert admitted == set(REQUIREMENT_FINGERPRINTS)
    assert admitted.isdisjoint(deferred_requirements)
    forbidden_targets = ("03-", "entra", "oidc", "figma", "canonical-import", "write-back")
    closure_targets = [
        f"{entry['closure']['plan_task']} {entry['closure']['node']}".casefold()
        for source in inventory.values()
        for entry in source.values()
    ]
    assert all(
        forbidden not in target for target in closure_targets for forbidden in forbidden_targets
    )


def _without_comments(source: str, *, shell: bool = False) -> str:
    if shell:
        return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", without_blocks)


def _openapi_operations() -> dict[str, dict[str, object]]:
    from verboflex.main import create_app

    operations: dict[str, dict[str, object]] = {}
    for path_item in create_app().openapi()["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operations[str(operation["operationId"])] = operation
    return operations


def _resolve_runtime_binding(reference: str) -> object:
    kind, target = reference.split(":", 1)
    if kind == "python":
        module_name, qualified_name = target.split(":", 1)
        resolved: object = importlib.import_module(module_name)
        for segment in qualified_name.split("."):
            resolved = getattr(resolved, segment)
        assert callable(resolved), f"runtime symbol is not callable: {reference}"
        return resolved
    if kind in {"typescript", "migration"}:
        path_text, symbol = target.rsplit(":", 1)
        path = REPOSITORY_ROOT / path_text
        assert path.is_file(), f"runtime source is absent: {path_text}"
        source = path.read_text(encoding="utf-8")
        if kind == "typescript":
            executable = _without_comments(source)
            declaration = re.compile(
                rf"^export\s+(?:async\s+)?function\s+{re.escape(symbol)}"
                r"(?:<[^>]+>)?\s*\(",
                re.M,
            )
            assert declaration.search(executable), f"TypeScript symbol is absent: {reference}"
            return symbol
        tree = ast.parse(source, filename=path_text)
        declarations = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assert symbol in declarations, f"migration symbol is absent: {reference}"
        return symbol
    if kind == "compose":
        current: object = yaml.safe_load(BASE_COMPOSE.read_text(encoding="utf-8"))
        for segment in target.split("."):
            assert isinstance(current, dict) and segment in current, (
                f"Compose symbol is absent: {reference}"
            )
            current = current[segment]
        assert current is not None, f"Compose symbol is empty: {reference}"
        return current
    if kind == "openapi":
        operations = _openapi_operations()
        assert target in operations, f"OpenAPI operation is absent: {target}"
        return operations[target]
    raise AssertionError(f"unsupported runtime binding kind: {kind}")


def _assert_executable_evidence(references: list[str]) -> None:
    collectable: list[str] = []
    normalized_e2e_source = " ".join(FRONTEND_E2E.read_text(encoding="utf-8").split())
    smoke_source = _without_comments(SMOKE_HARNESS.read_text(encoding="utf-8"), shell=True)
    for reference in references:
        if reference.startswith("e2e:"):
            title = reference.removeprefix("e2e:")
            assert f'test("{title}"' in normalized_e2e_source, f"E2E title is absent: {title}"
        elif reference.startswith("smoke:"):
            scenario = reference.removeprefix("smoke:")
            assert scenario in smoke_source, f"smoke scenario is absent: {scenario}"
            assert {
                "--mock-live-provider": "run_mock_live_provider",
                "--worker-loss": "run_worker_loss",
            }[scenario] in smoke_source
        else:
            collectable.append(reference)
    _assert_nodes_collect([{"test_nodes": collectable}])


def _admin_route_functions() -> list[tuple[Path, ast.AsyncFunctionDef | ast.FunctionDef]]:
    functions: list[tuple[Path, ast.AsyncFunctionDef | ast.FunctionDef]] = []
    route_root = BACKEND_SOURCE / "api" / "v1" / "routes"
    for path in sorted(route_root.glob("admin_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                for decorator in node.decorator_list
            ):
                functions.append((path, node))
    return functions


def _frontmatter_document(frontmatter: dict[str, Any], body: str = "# Fixture\n") -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}"


def _review_fixture(
    *,
    critical: int = 2,
    warning: int = 6,
    status: str = "issues_found",
) -> str:
    inventory = {
        **{
            f"CR-{number:02d}": {
                "disposition": "open" if number in {14, 15} and critical else "closed",
                "severity": "critical",
            }
            for number in range(1, 16)
        },
        **{
            f"WR-{number:02d}": {
                "disposition": "open" if number >= 3 else "closed",
                "severity": "warning",
            }
            for number in range(1, 9)
        },
    }
    frontmatter = {
        "phase": "02-admin-configuration",
        "findings": {
            "critical": critical,
            "warning": warning,
            "info": 0,
            "total": critical + warning,
        },
        "status": status,
        "review_inventory": inventory,
    }
    table_rows = []
    for key, record in inventory.items():
        disposition = record["disposition"].upper()
        severity = record["severity"].upper()
        table_rows.append(
            f"| {key} | **{disposition} — {severity}** | fixture authority | fixture evidence |"
        )
    body = "\n".join(
        [
            "# Review fixture",
            "",
            "### Current CR/WR Inventory Re-audit",
            "",
            "| Row | Current disposition | Authority | Evidence |",
            "| --- | --- | --- | --- |",
            *table_rows,
            "",
            "### ASVS 5.0 Level 1 Coverage",
        ]
    )
    return _frontmatter_document(frontmatter, body)


def _verifier_fixture(*, status: str = "gaps_found") -> str:
    complete = status == "passed"
    totals = {
        "phase_goal": 1,
        "roadmap_success_criteria": 8,
        "requirements": 15,
        "context_decisions": 23,
        "research_assumptions": 3,
        "spec_edge_rows": 54,
        "prohibitions": 9,
        "ui_considerations": 8,
        "bitbucket_capabilities": 44,
        "review_rows": 23,
    }
    inventories = {
        key: {
            "count": total
            if complete or key not in {"phase_goal", "roadmap_success_criteria", "requirements"}
            else {"phase_goal": 0, "roadmap_success_criteria": 5, "requirements": 13}[key],
            "total": total,
        }
        for key, total in totals.items()
    }
    frontmatter = {
        "phase": "02-admin-configuration",
        "status": status,
        "inventories": inventories,
        "review": {
            "status": "issues_found",
            "critical": 0 if complete else 2,
            "warning": 6,
            "info": 0,
            "open_blockers": [] if complete else ["CR-14", "CR-15"],
            "open_warnings": [
                "WR-03",
                "WR-04",
                "WR-05",
                "WR-06",
                "WR-07",
                "WR-08",
            ],
        },
        "gaps": []
        if complete
        else [
            {
                "truth": "CR-14 and CR-15 remain open",
                "status": "failed",
                "reason": "fixture blocker state",
            }
        ],
    }
    return _frontmatter_document(frontmatter, "# Verifier fixture\n")


def test_phase2_review_contract_uses_current_structured_inventory() -> None:
    """Current and critical-zero reports validate without a frozen prose appendix."""
    current = _review_findings()
    assert set(current) == {"findings", "inventory", "status"}, (
        "review outcome must come from the structured current inventory"
    )
    open_critical = {
        key
        for key, record in current["inventory"].items()
        if record["disposition"] == "open" and record["severity"] == "critical"
    }
    assert open_critical in ({"CR-14", "CR-15"}, set())
    assert current["findings"] == {
        "critical": len(open_critical),
        "warning": 6,
        "info": 0,
        "total": len(open_critical) + 6,
    }
    assert current["status"] == "issues_found"
    assert {
        key
        for key, record in current["inventory"].items()
        if record["disposition"] == "open" and record["severity"] == "warning"
    } == {f"WR-{number:02d}" for number in range(3, 9)}

    warning_only = _review_findings(_review_fixture(critical=0))
    assert warning_only["status"] == "issues_found"
    assert warning_only["findings"] == {
        "critical": 0,
        "warning": 6,
        "info": 0,
        "total": 6,
    }


def test_phase2_review_contract_rejects_inventory_and_count_mutants() -> None:
    """Missing, duplicate, hidden, and count-inconsistent review rows fail closed."""
    baseline = _review_fixture()
    frontmatter = yaml.safe_load(baseline.split("---", 2)[1])

    missing = copy.deepcopy(frontmatter)
    del missing["review_inventory"]["CR-14"]
    with pytest.raises(AssertionError):
        _review_findings(_frontmatter_document(missing, baseline.split("---", 2)[2]))

    hidden_warning = copy.deepcopy(frontmatter)
    hidden_warning["review_inventory"]["WR-08"]["disposition"] = "closed"
    with pytest.raises(AssertionError):
        _review_findings(_frontmatter_document(hidden_warning, baseline.split("---", 2)[2]))

    bad_count = copy.deepcopy(frontmatter)
    bad_count["findings"]["warning"] = 5
    bad_count["findings"]["total"] = 7
    with pytest.raises(AssertionError):
        _review_findings(_frontmatter_document(bad_count, baseline.split("---", 2)[2]))

    unsupported = copy.deepcopy(frontmatter)
    unsupported["status"] = "pass_with_warnings"
    with pytest.raises(AssertionError):
        _review_findings(_frontmatter_document(unsupported, baseline.split("---", 2)[2]))

    duplicate_yaml = baseline.replace(
        "  CR-01:\n",
        "  CR-01:\n    disposition: closed\n    severity: critical\n  CR-01:\n",
        1,
    )
    with pytest.raises(AssertionError):
        _review_findings(duplicate_yaml)


def test_phase2_verifier_contract_accepts_truthful_state_transitions() -> None:
    """Both current gaps and complete passed inventories are truthful states."""
    current = _verifier_groups()
    assert current["status"] == "gaps_found"
    assert current["review"]["open_blockers"] == ["CR-14", "CR-15"]
    assert len(current["gaps"]) == 2

    passed = _verifier_groups(_verifier_fixture(status="passed"))
    assert passed["status"] == "passed"
    assert passed["gaps"] == []
    assert all(record["count"] == record["total"] for record in passed["inventories"].values())


def test_phase2_verifier_contract_rejects_false_pass_and_status_mutants() -> None:
    """A passed label cannot hide gaps, incomplete totals, blockers, or warnings."""
    baseline = _verifier_fixture(status="passed")
    frontmatter = yaml.safe_load(baseline.split("---", 2)[1])

    incomplete = copy.deepcopy(frontmatter)
    incomplete["inventories"]["requirements"]["count"] = 14
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(incomplete))

    hidden_warning = copy.deepcopy(frontmatter)
    hidden_warning["review"]["open_warnings"].remove("WR-08")
    hidden_warning["review"]["warning"] = 5
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(hidden_warning))

    false_gap = copy.deepcopy(frontmatter)
    false_gap["gaps"] = [{"truth": "hidden gap", "status": "failed", "reason": "fixture"}]
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(false_gap))

    blockers = copy.deepcopy(frontmatter)
    blockers["review"]["critical"] = 1
    blockers["review"]["open_blockers"] = ["CR-14"]
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(blockers))

    unsupported = copy.deepcopy(frontmatter)
    unsupported["status"] = "complete"
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(unsupported))

    gaps_without_details = copy.deepcopy(frontmatter)
    gaps_without_details["status"] = "gaps_found"
    gaps_without_details["gaps"] = []
    with pytest.raises(AssertionError):
        _verifier_groups(_frontmatter_document(gaps_without_details))


def test_phase2_multi_source_coverage_contract() -> None:
    """Every canonical item retains meaning and reaches executable evidence."""
    inventory = _multi_source_inventory()
    _assert_shape(inventory)
    _assert_semantics(inventory)
    _assert_capability_rewrite(inventory)
    _assert_reachability(inventory)
    _assert_deferred_scope_rejected(inventory)
    _review_findings()
    _verifier_groups()


def test_phase2_audit_rejects_semantic_path_and_scope_mutations() -> None:
    """Equal counts cannot conceal changed meaning, invalid evidence, or deferred scope."""
    inventory = _multi_source_inventory()

    semantic_mutant = copy.deepcopy(inventory)
    semantic_mutant["decisions"]["D-01"]["semantic"] = _fingerprint("renamed meaning")
    with pytest.raises(AssertionError):
        _assert_semantics(semantic_mutant)

    path_mutant = copy.deepcopy(inventory)
    path_mutant["requirements"]["PROD-01"]["closure"]["node"] = (
        "backend/tests/architecture/not_a_test.py::test_missing"
    )
    with pytest.raises(AssertionError):
        _assert_reachability(path_mutant)

    deferred_mutant = copy.deepcopy(inventory)
    deferred_mutant["requirements"]["FMT-01"] = copy.deepcopy(
        deferred_mutant["requirements"]["PROD-01"]
    )
    with pytest.raises(AssertionError):
        _assert_shape(deferred_mutant)

    with pytest.raises(AssertionError):
        _unique([("D-01", "first"), ("D-01", "replacement")], source="mutation")


def test_phase2_gap_authorities_are_wired() -> None:
    """CR/WR and G1-G5 must reach production runtime authority, not prose."""
    assert GAP_RUNTIME_BINDINGS.keys() == EXPECTED_GAP_RUNTIME_KEYS
    for key, binding in GAP_RUNTIME_BINDINGS.items():
        assert set(binding) == {"runtime", "evidence"}, f"incomplete runtime row: {key}"
        _resolve_runtime_binding(binding["runtime"])
    _assert_executable_evidence([binding["evidence"] for binding in GAP_RUNTIME_BINDINGS.values()])

    from verboflex.schemas.admin_bitbucket import AdminBitbucketStatusResponse

    status_values = {
        "Disconnected",
        "Connected",
        "Reauthorization required",
        "Unavailable",
    }
    assert "status" in AdminBitbucketStatusResponse.model_fields
    schema = AdminBitbucketStatusResponse.model_json_schema()
    assert schema["required"] == [
        "status",
        "connected_at",
        "expires_at",
        "revoked_at",
    ]
    assert set(schema["properties"]["status"]["enum"]) == status_values

    operations = _openapi_operations()
    openapi_schema = operations["get_admin_bitbucket_status"]
    response_schema = openapi_schema["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/AdminBitbucketStatusResponse"}
    generated = (FRONTEND_SOURCE / "api" / "client" / "types.gen.ts").read_text(encoding="utf-8")
    generated_status = generated.split("export type AdminBitbucketStatusResponse = {", 1)[1].split(
        "\n};", 1
    )[0]
    assert re.search(r"^\s*status:\s*", generated_status, re.M)
    assert all(repr(value) in generated_status for value in status_values)
    bitbucket_page = _without_comments(
        (
            FRONTEND_SOURCE / "features" / "admin" / "bitbucket" / "BitbucketConnectionPage.tsx"
        ).read_text(encoding="utf-8")
    )
    workspace_page = _without_comments(
        (FRONTEND_SOURCE / "features" / "workspace" / "WorkspaceOverviewPage.tsx").read_text(
            encoding="utf-8"
        )
    )
    assert "connection.status" in bitbucket_page
    assert 'AdminBitbucketStatusResponse["status"]' in workspace_page


def test_phase2_forbidden_bypasses_are_absent() -> None:
    """Deferred authentication, provider-write, and canonical surfaces stay absent."""
    operations = _openapi_operations()
    bitbucket_operations = {
        operation_id for operation_id in operations if "bitbucket" in operation_id.casefold()
    }
    assert bitbucket_operations == {
        "get_admin_bitbucket_status",
        "connect_admin_bitbucket_oauth",
        "reconnect_admin_bitbucket_oauth",
        "revoke_admin_bitbucket_connection_locally",
    }
    assert not any(
        token in operation_id.casefold()
        for operation_id in bitbucket_operations
        for token in ("callback", "authorization_code", "refresh")
    )

    oauth_tree = ast.parse(
        (BACKEND_SOURCE / "services" / "bitbucket_oauth.py").read_text(encoding="utf-8")
    )
    oauth_methods = {
        node.name
        for node in ast.walk(oauth_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not {
        name
        for name in oauth_methods
        if any(token in name for token in ("callback", "authorization_code", "refresh"))
    }

    provider_violations: list[str] = []
    for path in sorted((BACKEND_SOURCE / "integrations" / "bitbucket").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in {"put", "patch", "delete"}:
                provider_violations.append(f"{path.name}:{node.lineno}:{node.func.attr}")
            if node.func.attr in {"request", "stream"}:
                method = node.args[0] if node.args else None
                if not isinstance(method, ast.Constant) or method.value != "GET":
                    provider_violations.append(f"{path.name}:{node.lineno}:non-static-provider-GET")
    assert provider_violations == []

    model_names = {
        path.stem.casefold()
        for path in (BACKEND_SOURCE / "models").glob("*.py")
        if path.name != "__init__.py"
    }
    assert not any(
        token in model_name
        for model_name in model_names
        for token in ("canonical", "translation", "import", "pull_request", "comment")
    )

    admin_routes = _admin_route_functions()
    assert len(admin_routes) == 34
    for path, function in admin_routes:
        annotations = {
            ast.unparse(argument.annotation)
            for argument in (*function.args.posonlyargs, *function.args.args)
            if argument.annotation is not None
        }
        assert "AdminPrincipal" in annotations, (
            f"administrator role dependency is absent: {path.name}:{function.name}"
        )

    router_source = _without_comments((FRONTEND_SOURCE / "router.tsx").read_text(encoding="utf-8"))
    assert "const guardedAdminElement = isAdmin ?" in router_source
    assert '<Route path="/admin/*" element={guardedAdminElement}' in router_source
    assert "<AdminApplicationRoutes" in router_source
