"""Real code-key import and approval commits with unrelated shared XML duplicates."""

import base64
import json
from pathlib import Path

from code_capture_smoke import HEAD, configure, setup
from phase7_smoke import write_json


def run(h):
    prefix = "shared-moko-e2e"
    configure(h, repository_prefix=prefix)
    control = json.loads(h.control_path.read_text())
    slug = f"{prefix}-translations"
    original = control["repositories"][slug]["files"]
    path = "shared/moko-resources/base/strings.xml"
    duplicates = (
        b'<!-- another product -->\r\n<string name="duplicate">First</string>\r\n'
        b'<string name="duplicate"><![CDATA[Second & unchanged]]></string>\r\n'
    )
    source = base64.b64decode(original["res/values/strings.xml"]).replace(
        b"</resources>", duplicates + b"</resources>"
    )
    working_head = "2" * 40
    working_source = source.replace(
        b"<resources>", b'<resources><string name="branch_only">Preserve me</string>'
    ).replace(b">Unrelated<", b">Existing branch change<")
    control["repositories"][slug]["files"] = {
        path: base64.b64encode(source).decode(),
        "shared/moko-resources/it/strings.xml": original["res/values-it/strings.xml"],
    }
    control.setdefault("branches", {})[slug] = {
        "feature/verboflex": working_head,
        "master": HEAD,
    }
    control.setdefault("files", {})[slug] = {
        working_head: {path: base64.b64encode(working_source).decode()}
    }
    h.control(
        repositories=control["repositories"],
        branches=control["branches"],
        files=control["files"],
    )
    repository_id = setup(h, repository_prefix=prefix)
    control["branches"].pop(slug)
    control["files"].pop(slug)
    h.control(branches=control["branches"], files=control["files"])
    product = h.fixture["code_capture"]["product"]
    source_mapping = h.fixture["code_capture"]["mapping"]
    endpoint = f"/products/{product}/branch-workflow"
    h.api(
        endpoint,
        "PUT",
        {
            "mapping_id": source_mapping,
            "work_branch": "feature/verboflex",
            "target_branch": "master",
        },
    )
    h.compose("up", "-d", "scheduler")
    groups = h.api(f"/translations?product_id={product}&language=en&page_size=50")[
        "items"
    ]
    details = [h.api(f"/translations/{item['id']}") for item in groups]
    group = next(d for d in details if d["raw_key"] == "title")
    commits = []
    parent = working_head
    expected_bytes = working_source
    previous_title = b"Base title"
    for text in (
        "First approved title",
        "Second approved title",
        "Conflicting third approval",
    ):
        if commits:
            parent = ("3" if len(commits) == 1 else "4") * 40
            if len(commits) == 1:
                expected_bytes = expected_bytes.replace(
                    b"</resources>", b"<!-- unrelated change --></resources>"
                )
            else:
                expected_bytes = expected_bytes.replace(previous_title, b"Edited by another user")
            h.control(
                branches={**control["branches"], slug: {"feature/verboflex": parent}},
                files={
                    **control["files"],
                    slug: {parent: {path: base64.b64encode(expected_bytes).decode()}},
                },
            )
            # Materialize the external revision, then let normal commits advance the fixture.
            page = h.api(f"/admin/repositories/{repository_id}/branches")
            assert {"name": "feature/verboflex", "commit_hash": parent} in page["items"]
            h.control(branches=control["branches"], files=control["files"])
        detail = h.api(f"/translations/{group['id']}")
        pending = detail["pending_change"]
        saved = h.api(
            f"/translations/{group['id']}/proposal",
            "PUT",
            {
                "expected_version": pending["version"] if pending else 0,
                "values": [
                    {
                        "translation_value_id": v["id"],
                        "proposed_text": text,
                        "selector_version": v["selector_version"],
                        "selector_digest": v["selector_digest"],
                        "basis_revision_number": v["history"][0]["revision_number"],
                        "basis_digest": v["history"][0]["revision_digest"],
                    }
                    for v in detail["values"]
                ],
            },
        )
        approval_url = f"/translations/{group['id']}/proposal/state"
        payload = {"expected_version": saved["version"], "target_state": "approved"}
        h.api(approval_url, "POST", payload)
        h.api(approval_url, "POST", payload, expected=409)
        result = h.wait(
            lambda: h.api(endpoint),
            lambda d: d["items"][0]["state"] in ("committed", "blocked"),
            seconds=120,
        )
        if len(commits) == 2:
            assert result["items"][0]["state"] == "blocked"
            assert result["items"][0]["error_code"] == "source_file_changed", result["items"][0]["error_code"]
            assert h.graph()["repositories"][slug]["counters"]["commit"]["effects"] == 2
            assert (
                h.graph()["repositories"][slug]["counters"]["pull_request"]["effects"]
                == 0
            )
            break
        assert result["items"][0]["state"] == "committed", (
            "shared_catalog_commit_failed"
        )
        sha = result["items"][0]["commit_hash"]
        repo = h.graph()["repositories"][slug]
        commit = repo["commits"][sha]
        assert commit["parents"] == [parent]
        expected_bytes = expected_bytes.replace(previous_title, text.encode())
        previous_title = text.encode()
        assert base64.b64decode(commit["files"][path]) == expected_bytes
        assert repo["counters"]["commit"]["effects"] == len(commits) + 1
        assert repo["counters"]["pull_request"]["effects"] == 0
        commits.append(sha)
    assert len(set(commits)) == 2
    write_json(
        Path(h.fixture["evidence_dir"]) / "shared-moko-approval-evidence.json",
        {
            "code_key_import": True,
            "commits": 2,
            "pull_requests": 0,
            "unrelated_duplicate_bytes_preserved": True,
            "existing_branch_changes_preserved": True,
            "later_unrelated_edit_preserved": True,
            "conflicting_external_title_blocked": True,
            "duplicate_approval_rejected": True,
        },
    )
