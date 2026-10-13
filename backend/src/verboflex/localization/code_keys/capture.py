"""Portable, closed capture bundle consumed inside the Android runner sandbox."""

import re
from collections import defaultdict
from typing import Annotated, Literal, cast
from xml.etree import ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verboflex.localization.code_keys.catalog import ComposeCaptureConfig
from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.schemas.screenshots import ScreenshotRequest


class CaptureValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[str, Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", max_length=255)]
    language: str
    selector: dict[str, object]
    text: Annotated[str, Field(max_length=65536)]


class CaptureBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    code_repository_id: str
    code_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40,64}$")]
    translations_repository_id: str
    translations_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40,64}$")]
    import_execution_id: str
    language: str
    base_language: str
    capture: ComposeCaptureConfig
    request: ScreenshotRequest
    values: Annotated[list[CaptureValue], Field(max_length=20000)]

    @field_validator("language", "base_language")
    @classmethod
    def locale(cls, locale: str) -> str:
        if normalize_preview_locale(locale) != locale:
            raise ValueError("Invalid capture locale")
        return locale


def preview_source(bundle: CaptureBundle, nonce: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise ValueError("Invalid render identity")
    function = bundle.request.preview_function
    if function not in bundle.capture.preview_functions:
        raise ValueError("Unregistered preview")
    night = "YES" if bundle.request.theme == "dark" else "NO"
    device = f"spec:width={bundle.capture.width_dp}dp,height={bundle.capture.height_dp}dp,dpi=160"
    return f'''package verboflex.capture
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import android.content.res.Configuration
import {function} as SelectedPreview

@PreviewTest
@Preview(name = "capture-{nonce}", device = "{device}", locale = "{bundle.language}",
    uiMode = Configuration.UI_MODE_NIGHT_{night}, fontScale = 1.0f)
@Composable
fun Capture() {{ SelectedPreview() }}
'''


def _android_text(text: str) -> str:
    # Resource XML quoting preserves whitespace and shields leading @ / ?. XML
    # metacharacters are escaped by ElementTree, Android escapes by this layer.
    return (
        '"'
        + text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        + '"'
    )


def resource_overlay(bundle: CaptureBundle) -> bytes:
    """Overlay selected locale, falling back to imported base per key/selector."""
    selected: dict[tuple[str, str], CaptureValue] = {}
    for locale in dict.fromkeys((bundle.base_language, bundle.language)):
        for value in bundle.values:
            if value.language != locale:
                continue
            kind = value.selector.get("kind")
            fields = value.selector.get("fields")
            if kind == "scalar" and fields == {}:
                identity = "scalar"
            elif kind in {"android_quantity", "android_array_item"} and isinstance(fields, dict):
                field = fields
                identity = str(
                    field.get("quantity") if kind == "android_quantity" else field.get("index")
                )
            else:
                raise ValueError("Capture requires Android resource selectors")
            selected[(value.key, identity)] = value
    resources = ET.Element("resources")
    groups: dict[str, list[tuple[str, CaptureValue]]] = defaultdict(list)
    for (key, identity), value in sorted(selected.items()):
        groups[key].append((identity, value))
    for key, values in groups.items():
        kinds = {v.selector["kind"] for _, v in values}
        if len(kinds) != 1:
            raise ValueError("Ambiguous Android resource structure")
        kind = kinds.pop()
        if kind == "scalar":
            ET.SubElement(resources, "string", name=key).text = _android_text(values[0][1].text)
        elif kind == "android_quantity":
            parent = ET.SubElement(resources, "plurals", name=key)
            for identity, value in values:
                if identity not in {"zero", "one", "two", "few", "many", "other"}:
                    raise ValueError("Invalid plural quantity")
                ET.SubElement(parent, "item", quantity=identity).text = _android_text(value.text)
        else:
            parent = ET.SubElement(resources, "string-array", name=key)
            ordered = sorted(values, key=lambda item: int(item[0]))
            if [int(index) for index, _ in ordered] != list(range(len(ordered))):
                raise ValueError("Incomplete resource array")
            for _, value in ordered:
                ET.SubElement(parent, "item").text = _android_text(value.text)
    return cast(bytes, ET.tostring(resources, encoding="utf-8", xml_declaration=True))
