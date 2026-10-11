"""Run with backend/.venv/bin/python mcp-server/generate_contract.py [--check]."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from verboflex.main import create_app  # noqa: E402

from verboflex_mcp.catalog import OPERATIONS, READ_ONLY_POST_OPERATIONS  # noqa: E402


def generate() -> dict[str, Any]:
    spec = create_app().openapi()
    schemas = spec["components"]["schemas"]
    result = {}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            identity = operation.get("operationId")
            if identity not in OPERATIONS:
                continue
            name, description = OPERATIONS[identity]
            properties = {}
            required = []
            bindings = {}
            for parameter in operation.get("parameters", []):
                if parameter["in"] not in {"path", "query"}:
                    raise ValueError(f"Unexpected parameter location for {identity}")
                key = parameter["name"]
                properties[key] = deepcopy(parameter["schema"])
                if parameter.get("description"):
                    properties[key]["description"] = parameter["description"]
                bindings[key] = parameter["in"]
                if parameter.get("required"):
                    required.append(key)
            if body := operation.get("requestBody"):
                assert "payload" not in properties
                properties["payload"] = deepcopy(body["content"]["application/json"]["schema"])
                if body.get("required"):
                    required.append("payload")
            schema: dict[str, Any] = {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            }
            if required:
                schema["required"] = required
            definitions: dict[str, Any] = {}

            def resolve(node: Any, definitions: dict[str, Any] = definitions) -> None:
                if isinstance(node, dict):
                    if ref := node.get("$ref"):
                        prefix = "#/components/schemas/"
                        assert ref.startswith(prefix)
                        key = ref.removeprefix(prefix)
                        node["$ref"] = f"#/$defs/{key}"
                        if key not in definitions:
                            definitions[key] = deepcopy(schemas[key])
                            resolve(definitions[key])
                    for value in node.values():
                        resolve(value)
                elif isinstance(node, list):
                    for value in node:
                        resolve(value)

            resolve(schema)
            if definitions:
                schema["$defs"] = definitions
            result[name] = {
                "operation_id": identity,
                "method": method.upper(),
                "read_only": method.upper() == "GET" or identity in READ_ONLY_POST_OPERATIONS,
                "path": path.removeprefix("/api/v1"),
                "bindings": bindings,
                "description": description,
                "input_schema": schema,
            }
    assert len(result) == len(OPERATIONS), "Allowlisted operation missing from API"
    return result


if __name__ == "__main__":
    destination = ROOT / "src/verboflex_mcp/contract.json"
    content = json.dumps(generate(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        if destination.read_text() != content:
            raise SystemExit("MCP contract is stale; run generate_contract.py")
        print("MCP contract matches backend OpenAPI")
    else:
        destination.write_text(content)
        print(f"Generated {len(OPERATIONS)} MCP tools")
