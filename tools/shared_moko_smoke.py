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
    control["repositories"][slug]["files"] = {
        path: base64.b64encode(source).decode(),
        "shared/moko-resources/it/strings.xml": original["res/values-it/strings.xml"],
    }
    control.setdefault("branches", {})[slug] = {
        "feature/verboflex": HEAD,
        "master": HEAD,
    }
    h.control(repositories=control["repositories"], branches=control["branches"])
    setup(h, repository_prefix=prefix)
    control["branches"].pop(slug)
    h.control(branches=control["branches"])
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
    for text in ("First approved title", "Second approved title"):
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
        assert result["items"][0]["state"] == "committed", (
            "shared_catalog_commit_failed"
        )
        sha = result["items"][0]["commit_hash"]
        repo = h.graph()["repositories"][slug]
        commit = repo["commits"][sha]
        assert commit["parents"] == [commits[-1] if commits else HEAD]
        assert base64.b64decode(commit["files"][path]) == source.replace(
            b"Base title", text.encode()
        )
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
            "duplicate_approval_rejected": True,
        },
    )
