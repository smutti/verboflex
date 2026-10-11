"""Independent state/counter/HTTP assertions for the disposable provider."""

import asyncio
import base64
import concurrent.futures
import importlib.util
import json
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
import pytest

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location(
    "phase7_mock_provider", TOOLS / "phase7_mock_provider.py"
)
assert SPEC is not None and SPEC.loader is not None
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)


def test_uuid_addressing_and_distinct_equal_byte_target_heads(tmp_path):
    control = tmp_path / "control.json"
    control.write_text(json.dumps({"heads": {"phase6-json": "1" * 40}}))
    graph = provider.Graph(tmp_path / "graph.json", control)
    identity = "{" + str(uuid5(NAMESPACE_URL, "acme/phase6-json")) + "}"
    status, repository, _ = graph.read("acme", identity, [], {})
    assert status == 200
    assert repository["full_name"] == "acme/phase6-json"
    status, branch, _ = graph.read("acme", identity, ["refs", "branches", "release"], {})
    assert status == 200 and branch["target"]["hash"] == "2" * 40
    assert branch["target"].get("repository") == repository
    one = graph.read("acme", identity, ["src", "1" * 40, "locales", "it.json"], {})
    two = graph.read("acme", identity, ["src", "2" * 40, "locales", "it.json"], {})
    assert one == two and one[0] == 200


def test_runtime_restart_is_visible_without_resetting_the_persisted_graph(tmp_path):
    control = tmp_path / "control.json"
    control.write_text(json.dumps({"heads": {"phase6-json": "1" * 40}}))
    graph = provider.Graph(tmp_path / "graph.json", control)
    graph.read("acme", "phase6-json", [], {})
    graph.started()
    original = graph.data["runtime"].copy()
    reopened = provider.Graph(graph.path, control)
    assert reopened.data["runtime"] == original
    reopened.started()
    assert reopened.data["runtime"]["boot_count"] == 2
    assert reopened.data["runtime"]["instance_id"] != original["instance_id"]
    assert reopened.data["repositories"] == graph.data["repositories"]


def test_control_reader_retries_transient_empty_bind_reads_without_reusing_old_state(
    tmp_path, monkeypatch
):
    control = tmp_path / "control.json"
    control.write_text('{"write_faults": {}}')
    graph = provider.Graph(tmp_path / "graph.json", control)
    assert graph.controls() == {"write_faults": {}}
    samples = iter(["", '{"write_faults":', '{"faults": {"fixture": "block"}}'])
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: next(samples))
    monkeypatch.setattr(provider.time, "sleep", lambda _seconds: None)
    assert graph.controls() == {"faults": {"fixture": "block"}}


def test_control_reader_rejects_persistently_invalid_json_after_bounded_reads(
    tmp_path, monkeypatch
):
    graph = provider.Graph(tmp_path / "graph.json", tmp_path / "control.json")
    reads = []

    def invalid_read(*_args, **_kwargs):
        reads.append(True)
        return ""

    monkeypatch.setattr(Path, "read_text", invalid_read)
    monkeypatch.setattr(provider.time, "sleep", lambda _seconds: None)
    with pytest.raises(json.JSONDecodeError):
        graph.controls()
    assert 1 < len(reads) <= 25


@pytest.fixture
def server(tmp_path, monkeypatch):
    control = tmp_path / "control.json"
    control.write_text(
        json.dumps({"heads": {"phase6-json": "1" * 40, "phase6-ios_strings": "1" * 40}})
    )
    for name, value in {
        "MOCK_AUDIT_FILE": tmp_path / "audit.jsonl",
        "MOCK_CONTROL_FILE": control,
        "MOCK_BLOCK_STARTED_FILE": tmp_path / "blocked",
        "MOCK_ACCESS_TOKEN": "isolated-token",
        "MOCK_CLIENT_ID": "isolated-client",
        "MOCK_CLIENT_SECRET": "isolated-secret",
    }.items():
        monkeypatch.setenv(name, str(value))
    script = (
        (TOOLS / "phase3_smoke.sh")
        .read_text()
        .split("cat >\"$SMOKE_PROVIDER_SCRIPT\" <<'PY'\n", 1)[1]
        .split("\nPY\n", 1)[0]
    )
    base = ModuleType("phase3_provider_for_test")
    # Execute the exact repository-owned fixture server, never provider input.
    exec(compile(script, "phase3_provider_for_test", "exec"), base.__dict__)  # noqa: S102
    graph = provider.Graph(tmp_path / "graph.json", control)
    handler = provider.install(base, graph)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(
        base_url=f"http://127.0.0.1:{httpd.server_port}",
        headers={"Authorization": "Bearer isolated-token"},
        timeout=5,
    ) as client:
        yield client, graph, control, base
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def url(slug="phase6-json"):
    return "/2.0/repositories/acme/{" + str(uuid5(NAMESPACE_URL, "acme/" + slug)) + "}"


def branch(client, name="generated", parent="2" * 40):
    return client.post(url() + "/refs/branches", json={"name": name, "target": {"hash": parent}})


def commit(client, *, name="generated", parent="2" * 40, content=b'{"changed":true}', fields=None):
    return client.post(
        url() + "/src",
        data={"branch": name, "parents": parent, "message": "exact marker"},
        files=fields or [("/locales/it.json", ("it.json", content, "application/octet-stream"))],
    )


def pr_body(commit_hash, name="generated"):
    repository = {"uuid": str(uuid5(NAMESPACE_URL, "acme/phase6-json"))}
    return {
        "title": "Approved",
        "description": "exact stable marker",
        "close_source_branch": False,
        "source": {
            "repository": repository,
            "branch": {"name": name},
            "commit": {"hash": commit_hash},
        },
        "destination": {"repository": repository, "branch": {"name": "release"}},
    }


def test_http_binary_commit_cas_absent_branch_and_persisted_exact_counters(server):
    client, graph, _, base = server
    created = branch(client)
    assert created.status_code == 201
    assert created.json()["target"]["repository"]["uuid"] == (
        "{" + str(uuid5(NAMESPACE_URL, "acme/phase6-json")) + "}"
    )
    assert branch(client).status_code == 409
    original = client.get(url() + "/src/" + "2" * 40 + "/locales/en.json").content
    response = commit(client)
    assert response.status_code == 201 and response.content == b""
    sha = client.get(url() + "/refs/branches/generated").json()["target"]["hash"]
    details = client.get(url() + "/commit/" + sha).json()
    assert details["message"] == "exact marker" and details["parents"] == [{"hash": "2" * 40}]
    assert client.get(url() + f"/src/{sha}/locales/en.json").content == original
    assert client.get(url() + f"/src/{sha}/locales/it.json").content == b'{"changed":true}'
    assert client.get(url() + f"/src/{sha}/locales/it.json?format=meta").json()["size"] == 16
    assert commit(client).status_code == 409
    assert commit(client, name="absent").status_code == 201
    reopened = provider.Graph(graph.path, graph.control)
    assert reopened.data["repositories"]["phase6-json"]["counters"] == {
        "branch": {"attempts": 2, "effects": 1},
        "commit": {"attempts": 3, "effects": 2},
        "pull_request": {"attempts": 0, "effects": 0},
    }
    audit = base.AUDIT.read_text()
    assert "isolated-token" not in audit and "changed" not in audit and "marker" not in audit


def test_production_write_adapter_accepts_complete_provider_receipts(server):
    import hashlib

    from verboflex.core.config import Settings
    from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
    from verboflex.integrations.bitbucket.writes import (
        BitbucketWriteAdapter,
        BranchIntent,
        CommitFile,
        CommitIntent,
        PullRequestIntent,
        WriteContext,
    )
    from verboflex.services.bitbucket_oauth import BitbucketCredentialLease

    client, graph, _, _ = server

    class Credentials:
        def acquire_repository_read_lease(self, session):
            return BitbucketCredentialLease(1, "isolated-token")

        def acquire_repository_write_lease(self, session, *, expected_generation):
            assert expected_generation == 1
            return self.acquire_repository_read_lease(session)

        def require_current_repository_read_lease(self, session, lease):
            assert lease.generation == 1

    def transport(request):
        response = client.request(
            request.method,
            request.url.raw_path.decode(),
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.content
        )

    async def run():
        reads = BitbucketHttpAdapter(
            settings=Settings(),
            credential_leases=Credentials(),
            transport=httpx.MockTransport(transport),
        )
        writes = BitbucketWriteAdapter(reads=reads)
        context = WriteContext(
            uuid5(NAMESPACE_URL, "acme/phase6-json"), "acme", "phase6-json", uuid4(), 1
        )
        branch_intent = BranchIntent(context, "2" * 40)
        try:
            assert (await writes.create_branch(None, intent=branch_intent)).state == "verified"
            original = client.get(url() + "/src/" + "2" * 40 + "/locales/it.json").content
            intent = CommitIntent(
                branch_intent,
                "f" * 64,
                (
                    CommitFile(
                        "locales/it.json", b'{"changed":true}', hashlib.sha256(original).hexdigest()
                    ),
                ),
            )
            committed = await writes.create_commit(None, intent=intent)
            assert committed.state == "verified", committed.code
            pr = PullRequestIntent(
                context, committed.receipt.commit_hash, "release", "2" * 40, "f" * 64
            )
            opened = await writes.create_pull_request(None, intent=pr)
            assert opened.state == "verified", opened.code
            recovered = await writes.reconcile_pull_request(None, intent=pr)
            assert recovered.state == "verified" and recovered.receipt == opened.receipt
        finally:
            await reads.aclose()

    asyncio.run(run())
    assert graph.data["repositories"]["phase6-json"]["counters"] == {
        operation: {"attempts": 1, "effects": 1} for operation in provider.OPERATIONS
    }


@pytest.mark.parametrize(
    "fields",
    [
        [("locales/it.json", ("it.json", b"bad", "application/octet-stream"))],
        [("/locales/../it.json", ("it.json", b"bad", "application/octet-stream"))],
        [("/locales/it.json", ("wrong.json", b"bad", "application/octet-stream"))],
        [("/locales/it.json", ("it.json", b"bad", "text/plain"))],
        [
            ("/locales/it.json", ("it.json", b"a", "application/octet-stream")),
            ("/locales/it.json", ("it.json", b"b", "application/octet-stream")),
        ],
    ],
)
def test_multipart_invalid_identity_is_rejected_without_effect(server, fields):
    client, graph, _, _ = server
    assert commit(client, fields=fields).status_code == 400
    assert graph.data["repositories"]["phase6-json"]["counters"]["commit"] == {
        "attempts": 1,
        "effects": 0,
    }


def test_utf16_metadata_and_changed_files_diffstat(server):
    client, _, _, _ = server
    raw = b"\xff\xfe" + '"test" = "è 🌍";'.encode("utf-16-le")
    prefix = url("phase6-ios_strings")
    response = client.post(
        prefix + "/src",
        data={"branch": "unicode", "parents": "2" * 40, "message": "unicode"},
        files=[
            (
                "/it.lproj/Localizable.strings",
                ("Localizable.strings", raw, "application/octet-stream"),
            )
        ],
    )
    assert response.status_code == 201
    sha = client.get(prefix + "/refs/branches/unicode").json()["target"]["hash"]
    assert client.get(prefix + f"/src/{sha}/it.lproj/Localizable.strings").content == raw
    assert client.get(prefix + f"/src/{sha}/it.lproj/Localizable.strings?format=meta").json()[
        "attributes"
    ] == ["binary"]
    diff = client.get(
        prefix + f"/diffstat/{sha}.." + "2" * 40,
        params={"pagelen": 100, "renames": "false", "topic": "false"},
    ).json()
    assert diff["size"] == 1 and diff["values"][0]["old"]["path"] == "it.lproj/Localizable.strings"


def test_pr_four_states_paginate_exactly_with_bound_query_and_identity(server):
    client, graph, control, _ = server
    assert commit(client).status_code == 201
    sha = client.get(url() + "/refs/branches/generated").json()["target"]["hash"]
    for _ in range(4):
        assert client.post(url() + "/pullrequests", json=pr_body(sha)).status_code == 201
    controls = json.loads(control.read_text())
    controls["pr_states"] = {
        "phase6-json": {
            str(i + 1): state
            for i, state in enumerate(("OPEN", "MERGED", "DECLINED", "SUPERSEDED"))
        }
    }
    control.write_text(json.dumps(controls))
    params = [
        ("pagelen", "2"),
        ("q", 'source.branch.name = "generated"'),
        *(("state", s) for s in sorted(provider.STATES)),
    ]
    first = client.get(url() + "/pullrequests", params=params).json()
    assert first["size"] == 4 and first["page"] == 1 and len(first["values"]) == 2
    next_url = httpx.URL(first["next"])
    second = client.get(next_url.raw_path.decode()).json()
    assert second["page"] == 2 and second["size"] == 4 and "next" not in second
    assert {pr["state"] for pr in first["values"] + second["values"]} == provider.STATES
    assert graph.data["repositories"]["phase6-json"]["counters"]["pull_request"] == {
        "attempts": 4,
        "effects": 4,
    }
    wrong = pr_body(sha)
    wrong["destination"]["repository"] = {"uuid": "00000000-0000-0000-0000-000000000001"}
    assert client.post(url() + "/pullrequests", json=wrong).status_code == 400


@pytest.mark.parametrize(
    "action", ["drop_after_apply", "block_after_apply", "block_before_apply", "reject"]
)
def test_faults_preserve_exact_attempts_and_delayed_effects(server, action):
    client, graph, control, base = server
    controls = json.loads(control.read_text())
    controls["write_faults"] = {
        "phase6-json": {"operation": "branch", "action": action, "token": "once"}
    }
    control.write_text(json.dumps(controls))
    if action.startswith("block"):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(branch, client)
            deadline = time.monotonic() + 3
            while not base.BLOCK_STARTED.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert base.BLOCK_STARTED.exists()
            counters = json.loads(graph.path.read_text())["repositories"]["phase6-json"][
                "counters"
            ]["branch"]
            assert counters == {"attempts": 1, "effects": int(action == "block_after_apply")}
            controls["write_faults"] = {}
            control.write_text(json.dumps(controls))
            assert future.result(timeout=3).status_code == 201
    elif action == "drop_after_apply":
        with pytest.raises(httpx.RemoteProtocolError):
            branch(client)
    else:
        assert branch(client).status_code == 403
    current = client.get(url() + "/refs/branches/generated")
    assert current.status_code == (404 if action == "reject" else 200)
    assert graph.data["repositories"]["phase6-json"]["counters"]["branch"] == {
        "attempts": 1,
        "effects": int(action != "reject"),
    }


def test_long_presentation_files_and_branch_overrides_are_independent_of_graph(tmp_path):
    path = "locales/" + "long" * 30 + "/it.json"
    content = json.dumps({"מפתח" * 45: "RTL value"}, ensure_ascii=False).encode()
    config = {
        "repositories": {"presentation": {"files": {path: base64.b64encode(content).decode()}}},
        "branches": {"presentation": {"long/source": "1" * 40, "long/target": "2" * 40}},
    }
    control = tmp_path / "control.json"
    control.write_text(json.dumps(config))
    graph = provider.Graph(tmp_path / "graph.json", control)
    assert graph.read("acme", "presentation", ["src", "2" * 40, path], {})[1] == content
    assert (
        graph.read("acme", "presentation", ["refs", "branches", "long/target"], {})[1]["target"][
            "hash"
        ]
        == "2" * 40
    )
    config["branches"]["presentation"]["long/source"] = None
    control.write_text(json.dumps(config))
    assert graph.read("acme", "presentation", ["refs", "branches", "long/source"], {})[0] == 404
    assert graph.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("disconnect", ["timeout", "socket_close"])
def test_delayed_commit_survives_client_loss_and_absent_branch_before_release(server, disconnect):
    client, graph, control, base = server
    slug = "phase7-late"
    branch_name = "verboflex/change-set-" + str(uuid4())
    controls = json.loads(control.read_text())
    controls["repositories"] = {slug: {"fixture": "json"}}

    def publish():
        temporary = control.with_suffix(".next")
        temporary.write_text(json.dumps(controls))
        temporary.replace(control)

    publish()
    prefix = url(slug)
    assert (
        client.post(
            prefix + "/refs/branches", json={"name": branch_name, "target": {"hash": "1" * 40}}
        ).status_code
        == 201
    )
    controls["write_faults"] = {
        slug: {
            "operation": "commit",
            "action": "block_before_apply",
            "token": "original",
            "seconds": 120,
        }
    }
    publish()
    request = client.build_request(
        "POST",
        prefix + "/src",
        data={"branch": branch_name, "parents": "1" * 40, "message": "original delayed commit"},
        files=[("/locales/it.json", ("it.json", b'{"late":true}', "application/octet-stream"))],
        timeout=0.15,
    )
    body = request.read()
    try:
        if disconnect == "timeout":
            with pytest.raises(httpx.ReadTimeout):
                client.send(request)
        else:
            connection = socket.create_connection(
                (client.base_url.host, client.base_url.port), timeout=2
            )
            with connection:
                headers = "\r\n".join(f"{key}: {value}" for key, value in request.headers.items())
                connection.sendall(
                    f"POST {request.url.raw_path.decode()} HTTP/1.1\r\n{headers}\r\n\r\n".encode()
                    + body
                )
        marker = Path(str(base.BLOCK_STARTED) + "." + slug + ".commit")
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "original POST never reached its before-apply barrier"
        controls["branches"] = {slug: {branch_name: None}}
        publish()
        assert client.get(prefix + "/refs/branches/" + branch_name).status_code == 404
        assert graph.data["repositories"][slug]["counters"]["commit"] == {
            "attempts": 1,
            "effects": 0,
        }
        controls["branches"], controls["write_faults"] = {}, {}
        publish()
        deadline = time.monotonic() + 3
        while (
            graph.data["repositories"][slug]["counters"]["commit"]["effects"] == 0
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert graph.data["repositories"][slug]["counters"]["commit"] == {
            "attempts": 1,
            "effects": 1,
        }
        response = client.get(prefix + "/refs/branches/" + branch_name)
        assert response.status_code == 200
        sha = response.json()["target"]["hash"]
        assert client.get(prefix + "/commit/" + sha).json()["parents"] == [{"hash": "1" * 40}]
        assert client.get(prefix + f"/src/{sha}/locales/it.json").content == b'{"late":true}'
        diagnostic = json.loads(graph.path.read_text())
        assert diagnostic["runtime"]["boot_count"] == 1
        assert diagnostic["fault_progress"][slug]["commit"] == {
            "instance_id": diagnostic["runtime"]["instance_id"],
            "phase": "applied",
            "release_reason": "control_changed",
            "apply_status": 201,
        }
        persisted = diagnostic["repositories"][slug]
        assert persisted["counters"]["commit"] == {"attempts": 1, "effects": 1}
    finally:
        controls["write_faults"] = {}
        publish()
