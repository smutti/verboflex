"""Stateful TLS Bitbucket fixture used only by the owned disposable smoke.

Private control and graph JSON are separate: replacing controls never resets
effects. Counters count every authenticated POST and every actual effect; this
fake deliberately does not implement client idempotency. No request body,
credential, file bytes or provider URL enters the base provider audit.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import socket
import threading
import time
from contextlib import suppress
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from phase6_smoke import DUPLICATE, DUPLICATE_PATH, fixture_files

HEAD = "1" * 40
RELEASE = "2" * 40
JSON = "application/json"
STATES = {"OPEN", "MERGED", "DECLINED", "SUPERSEDED"}
OPERATIONS = {"branch", "commit", "pull_request"}
MAX_BODY = 21 * 1024 * 1024


def _encoded(files):
    return {
        path: base64.b64encode(content).decode("ascii")
        for path, content in files.items()
    }


def _path(path):
    return (
        isinstance(path, str)
        and 0 < len(path) <= 2048
        and not any(part in {"", ".", ".."} for part in path.split("/"))
        and not any(char in path for char in '\\"\r\n\x00')
    )


def multipart(body, content_type):
    """Parse real binary multipart; reject aliases, duplicates and implicit deletes."""
    if len(body) > MAX_BODY or not content_type.startswith("multipart/form-data;"):
        raise ValueError("invalid multipart")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: "
        + content_type.encode("ascii")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )
    if not message.is_multipart() or message.defects:
        raise ValueError("invalid multipart")
    fields, files = {}, {}
    for part in message.iter_parts():
        if part.defects or part.get_content_disposition() != "form-data":
            raise ValueError("invalid part")
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True)
        if not isinstance(name, str) or not isinstance(payload, bytes):
            raise TypeError("invalid part")
        if name in {"branch", "parents", "message"}:
            if name in fields or part.get_filename() is not None:
                raise ValueError("duplicate field")
            fields[name] = payload.decode("utf-8")
        elif name.startswith("/") and _path(name[1:]):
            path = name[1:]
            if path in files or part.get_filename() != path.rsplit("/", 1)[-1]:
                raise ValueError("invalid file identity")
            if (
                part.get_content_type() != "application/octet-stream"
                or len(payload) > 1048576
            ):
                raise ValueError("invalid file")
            files[path] = payload
        else:
            raise ValueError("unknown multipart field")
    if set(fields) != {"branch", "parents", "message"} or not 1 <= len(files) <= 500:
        raise ValueError("incomplete multipart")
    if sum(map(len, files.values())) > 20 * 1048576:
        raise ValueError("too many bytes")
    return fields, files


class Graph:
    def __init__(self, path, control):
        self.path, self.control = Path(path), Path(control)
        self.lock = (
            threading.RLock()
        )  # Deliberately independent from the base audit lock.
        self.data = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {"version": 1, "repositories": {}, "consumed_faults": []}
        )
        if self.data.get("version") != 1:
            raise ValueError("unknown graph version")

    def controls(self):
        # Docker Desktop bind mounts can expose an empty/partial read during a
        # host atomic rename, even after fsync. Never substitute cached controls:
        # retry only malformed JSON for at most 240 ms, then reject as before.
        for attempt in range(25):
            try:
                return json.loads(self.control.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                if attempt == 24:
                    raise
                time.sleep(0.01)

    def started(self):
        """Private diagnostics distinguish a restarted process from a held request."""
        with self.lock:
            self.data["runtime"] = {
                "instance_id": str(uuid4()),
                "boot_count": self.data.get("runtime", {}).get("boot_count", 0) + 1,
            }
            self._save()

    def progress(self, slug, operation, phase, **fields):
        # Only fixed labels/statuses enter these bounded, latest-operation records.
        with self.lock:
            progress = self.data.setdefault("fault_progress", {}).setdefault(slug, {})
            record = progress.setdefault(operation, {})
            if phase.startswith("waiting_"):
                record.clear()
            record.update(
                instance_id=self.data["runtime"]["instance_id"], phase=phase, **fields
            )
            self._save()

    def _save(self):
        temporary = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(self.data, stream, separators=(",", ":"), sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def _repository(self, workspace, identity):
        control = self.controls()
        configurations = {slug: {} for slug in control.get("heads", {})}
        configurations.update(control.get("repositories", {}))
        for slug, config in configurations.items():
            if isinstance(config, str):
                config = {"fixture": config}
            configured_workspace = config.get("workspace", workspace)
            identifier = str(
                UUID(
                    config.get(
                        "uuid",
                        str(uuid5(NAMESPACE_URL, f"{configured_workspace}/{slug}")),
                    )
                )
            )
            if workspace != configured_workspace or identity not in {
                slug,
                identifier,
                "{" + identifier + "}",
            }:
                continue
            repo = self.data["repositories"].get(slug)
            if repo is None:
                fixture = config.get(
                    "fixture",
                    "json" if "files" in config else slug.removeprefix("phase6-"),
                )
                files = config.get("files", _encoded(fixture_files(fixture)))
                if not isinstance(files, dict) or not files:
                    raise ValueError("invalid fixture files")
                for path, content in files.items():
                    if not _path(path):
                        raise ValueError("invalid fixture path")
                    base64.b64decode(content, validate=True)
                repo = {
                    "uuid": identifier,
                    "workspace": workspace,
                    "slug": slug,
                    "fixture": fixture,
                    "branches": {"main": HEAD, "release": RELEASE},
                    "commits": {
                        HEAD: {
                            "files": files,
                            "parents": [],
                            "message": "Initial fixture",
                        },
                        RELEASE: {
                            "files": copy.deepcopy(files),
                            "parents": [HEAD],
                            "message": "Release base",
                        },
                    },
                    "pull_requests": {},
                    "counters": {
                        op: {"attempts": 0, "effects": 0} for op in OPERATIONS
                    },
                }
                self.data["repositories"][slug] = repo
            if repo["uuid"] != identifier or repo["workspace"] != workspace:
                return None
            overrides = dict(control.get("branches", {}).get(slug, {}))
            if slug in control.get("heads", {}):
                overrides["main"] = control["heads"][slug]
            for branch, commit in overrides.items():
                if commit is None:
                    repo["branches"].pop(branch, None)
                else:
                    if not re.fullmatch(r"[0-9a-f]{40}", commit):
                        raise ValueError("invalid controlled commit")
                    if commit not in repo["commits"]:
                        repo["commits"][commit] = copy.deepcopy(repo["commits"][HEAD])
                        repo["commits"][commit]["parents"] = [HEAD]
                    repo["branches"][branch] = commit
            for commit, changed in control.get("files", {}).get(slug, {}).items():
                for path, content in changed.items():
                    if not _path(path):
                        raise ValueError("invalid controlled path")
                    if content is None:
                        repo["commits"][commit]["files"].pop(path, None)
                    else:
                        base64.b64decode(content, validate=True)
                        repo["commits"][commit]["files"][path] = content
            for number, state in control.get("pr_states", {}).get(slug, {}).items():
                if state not in STATES:
                    raise ValueError("invalid controlled PR state")
                if str(number) in repo["pull_requests"]:
                    repo["pull_requests"][str(number)]["state"] = state
            self._save()
            return repo
        return None

    @staticmethod
    def metadata(repo):
        return {
            "type": "repository",
            "uuid": "{" + repo["uuid"] + "}",
            "full_name": f"{repo['workspace']}/{repo['slug']}",
            "scm": "git",
        }

    @staticmethod
    def _page(repo, resource, query, values):
        page = int(query.get("page", ["1"])[0])
        size = int(query.get("pagelen", ["100"])[0])
        if not 1 <= page <= 1000 or not 1 <= size <= 100:
            raise ValueError("invalid pagination")
        result = {
            "page": page,
            "pagelen": size,
            "size": len(values),
            "values": values[(page - 1) * size : page * size],
        }
        if page * size < len(values):
            params = {**query, "page": [str(page + 1)]}
            path = "/".join(quote(part, safe="") for part in resource)
            result["next"] = (
                f"https://api.bitbucket.org/2.0/repositories/{repo['workspace']}/{repo['slug']}/{path}?"
                + urlencode(params, doseq=True)
            )
        return result

    def read(self, workspace, identity, resource, query):
        with self.lock:
            repo = self._repository(workspace, identity)
            if repo is None:
                return 404, {"error": "not_found"}, JSON
            if not resource:
                return 200, self.metadata(repo), JSON
            if resource[:2] == ["refs", "branches"]:
                if len(resource) == 2:
                    values = [
                        {"type": "branch", "name": name, "target": {"hash": sha}}
                        for name, sha in sorted(repo["branches"].items())
                    ]
                    return 200, self._page(repo, resource, query, values), JSON
                branch = "/".join(resource[2:])
                if branch in repo["branches"]:
                    return (
                        200,
                        {
                            "type": "branch",
                            "name": branch,
                            "target": {
                                "hash": repo["branches"][branch],
                                "repository": self.metadata(repo),
                            },
                        },
                        JSON,
                    )
            elif resource[:1] == ["commit"] and len(resource) == 2:
                commit = repo["commits"].get(resource[1])
                if commit:
                    return (
                        200,
                        {
                            "hash": resource[1],
                            "message": commit["message"],
                            "parents": [{"hash": p} for p in commit["parents"]],
                            "repository": self.metadata(repo),
                        },
                        JSON,
                    )
            elif resource[:1] == ["commits"] and len(resource) == 2:
                values, todo, seen = [], [resource[1]], set()
                while todo:
                    sha = todo.pop(0)
                    if sha not in seen and sha in repo["commits"]:
                        seen.add(sha)
                        values.append({"hash": sha})
                        todo.extend(repo["commits"][sha]["parents"])
                return 200, self._page(repo, resource, query, values), JSON
            elif resource[:1] == ["diffstat"] and len(resource) == 2:
                ends = resource[1].split("..")
                if len(ends) == 2 and all(sha in repo["commits"] for sha in ends):
                    new, old = (repo["commits"][sha]["files"] for sha in ends)
                    values = []
                    for path in sorted(set(old) | set(new)):
                        if old.get(path) != new.get(path):
                            values.append(
                                {
                                    "status": "modified"
                                    if path in old and path in new
                                    else "added"
                                    if path in new
                                    else "removed",
                                    "old": {"type": "commit_file", "path": path}
                                    if path in old
                                    else None,
                                    "new": {"type": "commit_file", "path": path}
                                    if path in new
                                    else None,
                                }
                            )
                    return 200, self._page(repo, resource, query, values), JSON
            elif resource[:1] == ["src"] and len(resource) >= 2:
                sha, path = resource[1], "/".join(resource[2:]).strip("/")
                commit = repo["commits"].get(sha)
                if commit:
                    files = commit["files"]
                    if "pagelen" in query:
                        values = [
                            {
                                "type": "commit_file",
                                "path": p,
                                "size": len(base64.b64decode(b)),
                            }
                            for p, b in sorted(files.items())
                            if not path or p.startswith(path + "/")
                        ]
                        return 200, self._page(repo, resource, query, values), JSON
                    content = (
                        DUPLICATE
                        if path == DUPLICATE_PATH
                        else base64.b64decode(files[path])
                        if path in files
                        else None
                    )
                    if content is not None:
                        if query == {"format": ["meta"]}:
                            return (
                                200,
                                {
                                    "type": "commit_file",
                                    "path": path,
                                    "commit": {"hash": sha},
                                    "size": len(content),
                                    "attributes": ["binary"]
                                    if content.startswith((b"\xff\xfe", b"\xfe\xff"))
                                    else [],
                                },
                                JSON,
                            )
                        if self.controls().get("tamper") == repo["slug"]:
                            content = content.replace(b"P6 old", b"P6 bad")
                        return 200, content, "application/octet-stream"
            elif resource[:1] == ["pullrequests"]:
                if (
                    len(resource) == 4
                    and resource[1] in repo["pull_requests"]
                    and resource[2:] == ["mergeability", "checks"]
                ):
                    # Synthetic writes have a clean merge unless the scenario
                    # explicitly injects conflicts or an unavailable check.
                    merge = (
                        self.controls()
                        .get("mergeability", {})
                        .get(repo["slug"], "clean")
                    )
                    checks = (
                        []
                        if merge == "unknown"
                        else [
                            {
                                "type": "git_mergeability_check",
                                "status": "PASSED" if merge == "clean" else "FAILED",
                                "reason": "clean" if merge == "clean" else "conflicts",
                                "blocking": merge != "clean",
                            }
                        ]
                    )
                    return 200, {"values": checks}, JSON
                if len(resource) == 2 and resource[1] in repo["pull_requests"]:
                    return 200, copy.deepcopy(repo["pull_requests"][resource[1]]), JSON
                if len(resource) == 1:
                    states = set(query.get("state", ["OPEN"]))
                    if not states <= STATES:
                        raise ValueError("invalid PR state")
                    filter_query = query.get("q", [None])[0]
                    branch = None
                    if filter_query is not None:
                        match = re.fullmatch(
                            r'source\.branch\.name = "([^"\\]+)"', filter_query
                        )
                        if match is None:
                            raise ValueError("invalid PR filter")
                        branch = match[1]
                    values = [
                        copy.deepcopy(pr)
                        for pr in repo["pull_requests"].values()
                        if pr["state"] in states
                        and (branch is None or pr["source"]["branch"]["name"] == branch)
                    ]
                    values.sort(key=lambda pr: pr["id"])
                    return 200, self._page(repo, resource, query, values), JSON
            return 404, {"error": "not_found"}, JSON

    def begin_write(self, workspace, identity, operation):
        with self.lock:
            repo = self._repository(workspace, identity)
            if repo is None or operation not in OPERATIONS:
                return None, None
            repo["counters"][operation]["attempts"] += 1
            controls = self.controls().get("write_faults", {})
            fault = controls.get(repo["slug"], controls.get("*"))
            if not isinstance(fault, dict) or fault.get("operation") != operation:
                fault = None
            if fault is not None:
                key = json.dumps([repo["slug"], operation, fault], sort_keys=True)
                if key in self.data["consumed_faults"]:
                    fault = None
                else:
                    self.data["consumed_faults"].append(key)
            self._save()
            return repo["slug"], copy.deepcopy(fault)

    def apply(self, workspace, identity, operation, payload, files=None):
        with self.lock:
            repo = self._repository(workspace, identity)
            if repo is None:
                return 404, {"error": "not_found"}, JSON
            if operation == "branch":
                if set(payload) != {"name", "target"} or set(payload["target"]) != {
                    "hash"
                }:
                    raise ValueError("invalid branch")
                branch, parent = payload["name"], payload["target"]["hash"]
                if (
                    not isinstance(branch, str)
                    or not 1 <= len(branch) <= 255
                    or parent not in repo["commits"]
                ):
                    raise ValueError("invalid branch")
                if branch in repo["branches"]:
                    return 409, {"error": "branch_exists"}, JSON
                repo["branches"][branch] = parent
                result = {
                    "type": "branch",
                    "name": branch,
                    "target": {"hash": parent, "repository": self.metadata(repo)},
                }
            elif operation == "commit":
                if set(payload) != {"branch", "parents", "message"} or not files:
                    raise ValueError("invalid commit")
                branch, parent = payload["branch"], payload["parents"]
                if (
                    parent not in repo["commits"]
                    or not isinstance(branch, str)
                    or not 1 <= len(branch) <= 255
                ):
                    raise ValueError("invalid parent")
                if branch in repo["branches"] and repo["branches"][branch] != parent:
                    return 409, {"error": "parent_conflict"}, JSON
                changed = {**repo["commits"][parent]["files"], **_encoded(files)}
                commit = {
                    "parents": [parent],
                    "message": payload["message"],
                    "files": changed,
                }
                # Deliberately unique per effect: an accidental duplicate POST is visible.
                sha = hashlib.sha1(
                    json.dumps(
                        [commit, repo["counters"][operation]["effects"]], sort_keys=True
                    ).encode()
                ).hexdigest()
                repo["commits"][sha] = commit
                repo["branches"][branch] = sha  # API creates an absent named branch.
                result = b""  # Source API permits an empty 201 response.
            elif operation == "pull_request":
                if (
                    set(payload)
                    != {
                        "title",
                        "description",
                        "source",
                        "destination",
                        "close_source_branch",
                    }
                    or payload["close_source_branch"] is not False
                ):
                    raise ValueError("invalid PR")
                for side in ("source", "destination"):
                    value = payload[side]
                    expected_keys = (
                        {"repository", "branch", "commit"}
                        if side == "source"
                        else {"repository", "branch"}
                    )
                    if set(value) != expected_keys or set(value["repository"]) != {
                        "uuid"
                    }:
                        raise ValueError("invalid repository")
                    if UUID(value["repository"]["uuid"]) != UUID(repo["uuid"]):
                        raise ValueError("wrong repository")
                source, target = (
                    payload[side]["branch"]["name"]
                    for side in ("source", "destination")
                )
                if (
                    source not in repo["branches"]
                    or target not in repo["branches"]
                    or source == target
                ):
                    raise ValueError("unknown branch")
                if payload["source"]["commit"] != {"hash": repo["branches"][source]}:
                    return 409, {"error": "source_changed"}, JSON
                number = max(map(int, repo["pull_requests"]), default=0) + 1
                result = {
                    "type": "pullrequest",
                    "id": number,
                    "state": "OPEN",
                    "title": payload["title"],
                    "description": payload["description"],
                    "links": {
                        "html": {
                            "href": f"https://bitbucket.org/{workspace}/{repo['slug']}/pull-requests/{number}"
                        }
                    },
                    **{
                        side: {
                            "repository": self.metadata(repo),
                            "branch": {"name": branch},
                            "commit": {"hash": repo["branches"][branch]},
                        }
                        for side, branch in (
                            ("source", source),
                            ("destination", target),
                        )
                    },
                }
                repo["pull_requests"][str(number)] = result
            else:
                raise ValueError("unknown operation")
            repo["counters"][operation]["effects"] += 1
            self._save()
            return (
                201,
                copy.deepcopy(result),
                "application/octet-stream" if operation == "commit" else JSON,
            )


def install(base, graph):
    """Install only the isolated provider handler; reuse OAuth, TLS and safe audit."""
    original = base.Handler
    graph.started()

    class Handler(original):
        def coordinates(self):
            parsed = urlsplit(self.path)
            if not parsed.path.startswith("/2.0/repositories/"):
                raise ValueError("unknown route")
            parts = [
                unquote(p)
                for p in parsed.path.removeprefix("/2.0/repositories/")
                .strip("/")
                .split("/")
            ]
            if len(parts) < 2:
                raise ValueError("unknown route")
            return parts[0], parts[1], parts[2:], parse_qs(parsed.query)

        def respond(self, method, family, response):
            status, payload, media_type = response
            base.record(
                category="resource",
                method=method,
                resource_family=family,
                status=status,
            )
            self.reply(status, payload, media_type=media_type)

        def do_GET(self):
            if urlsplit(self.path).path == "/_health":
                return original.do_GET(self)
            if not self.authorized():
                return
            try:
                workspace, identity, resource, query = self.coordinates()
                with graph.lock:
                    repo = graph._repository(workspace, identity)
                    slug = repo["slug"] if repo else identity
                fault = graph.controls().get("faults", {}).get(slug)
                statuses = {
                    "permission_denied": 403,
                    "rate_limited": 429,
                    "not_found": 404,
                    "timeout": 504,
                    "unavailable": 503,
                }
                if fault == "block":
                    base.BLOCK_STARTED.touch(mode=0o600, exist_ok=True)
                    deadline = time.monotonic() + 60
                    while (
                        graph.controls().get("faults", {}).get(slug) == "block"
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.05)
                    fault = "timeout"
                if fault in statuses:
                    response = statuses[fault], {"error": "bounded_failure"}, JSON
                else:
                    response = graph.read(workspace, identity, resource, query)
                family = (
                    "source-metadata"
                    if query == {"format": ["meta"]}
                    else self.family(resource)
                )
                self.respond("GET", family, response)
            except ValueError, KeyError, TypeError:
                self.respond(
                    "GET", "invalid-request", (400, {"error": "invalid_request"}, JSON)
                )

        def wait_fault(self, slug, fault, apply_status=None):
            side = (
                "before_apply"
                if fault["action"].endswith("before_apply")
                else "after_apply"
            )
            fields = {"apply_status": apply_status} if apply_status is not None else {}
            graph.progress(slug, fault["operation"], "waiting_" + side, **fields)
            marker = Path(
                str(base.BLOCK_STARTED) + "." + slug + "." + fault["operation"]
            )
            marker.touch(mode=0o600)
            base.BLOCK_STARTED.touch(mode=0o600, exist_ok=True)
            deadline = time.monotonic() + min(float(fault.get("seconds", 60)), 120)
            reason = "deadline"
            while time.monotonic() < deadline:
                current = graph.controls().get("write_faults", {})
                if current.get(slug, current.get("*")) != fault:
                    reason = "control_changed"
                    break
                time.sleep(0.05)
            graph.progress(
                slug, fault["operation"], "released_" + side, release_reason=reason
            )

        def do_POST(self):
            if urlsplit(self.path).path == "/site/oauth2/access_token":
                return original.do_POST(self)
            if not self.authorized():
                return
            operation = "invalid-request"
            slug, fault = None, None
            try:
                workspace, identity, resource, query = self.coordinates()
                operation = {
                    ("refs", "branches"): "branch",
                    ("src",): "commit",
                    ("pullrequests",): "pull_request",
                }.get(tuple(resource))
                if operation is None or query:
                    raise ValueError("unknown operation")
                slug, fault = graph.begin_write(workspace, identity, operation)
                if slug is None:
                    return self.respond(
                        "POST", operation, (404, {"error": "not_found"}, JSON)
                    )
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("invalid size")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("incomplete request")
                content_type = self.headers.get("Content-Type", "")
                if operation == "commit":
                    payload, files = multipart(body, content_type)
                else:
                    if content_type != JSON:
                        raise ValueError("invalid media")
                    payload, files = json.loads(body), None
                action = fault.get("action") if fault else None
                if action == "reject":
                    return self.respond(
                        "POST",
                        operation,
                        (403, {"error": "controlled_rejection"}, JSON),
                    )
                if action in {"block_before_apply", "delay_before_apply"}:
                    self.wait_fault(slug, fault)
                response = graph.apply(workspace, identity, operation, payload, files)
                if fault:
                    graph.progress(slug, operation, "applied", apply_status=response[0])
                if action in {"block_after_apply", "delay_after_apply"}:
                    self.wait_fault(slug, fault, apply_status=response[0])
                if action == "drop_after_apply":
                    base.record(
                        category="resource",
                        method="POST",
                        resource_family=operation,
                        status=response[0],
                    )
                    self.close_connection = True
                    with suppress(OSError):
                        self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.respond("POST", operation, response)
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                if slug and fault:
                    trace = error.__traceback__
                    while trace.tb_next is not None:
                        trace = trace.tb_next
                    graph.progress(
                        slug,
                        operation,
                        "rejected",
                        apply_status=400,
                        exception_type=type(error).__name__,
                        exception_file=Path(trace.tb_frame.f_code.co_filename).name,
                        exception_line=trace.tb_lineno,
                    )
                self.respond(
                    "POST",
                    operation or "invalid-request",
                    (400, {"error": "invalid_request"}, JSON),
                )

    base.Handler = Handler
    return Handler


def provider():
    import phase3_provider_base as base

    path = os.environ.get(
        "PHASE7_PROVIDER_GRAPH", str(base.CONTROL.with_name("provider-graph.json"))
    )
    install(base, Graph(path, base.CONTROL))
    base.main()


if __name__ == "__main__":
    provider()
