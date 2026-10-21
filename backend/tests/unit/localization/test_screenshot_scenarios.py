"""Explicit screen states take precedence over conservative static call evidence."""

import pytest
from pydantic import ValidationError

from verboflex.localization.code_keys.catalog import CodeSourceConfig, extract_catalog
from verboflex.services.screenshots import screen_scenarios

SOURCE = {
    "Screen.kt": b"""package demo
fun Login() { Res.strings.email; Modal() }
fun Modal() { Res.strings.privacy_notice }
@Preview @Composable fun LoginPreview() { Login() }
@Preview @Composable fun RegisterPreview() { Login() }
"""
}


def config(scenarios=()):
    return CodeSourceConfig.model_validate(
        {
            "compose": {
                "runner_profile": "synthetic",
                "preview_functions": ["demo.LoginPreview", "demo.RegisterPreview"],
            },
            "preview_scenarios": scenarios,
        }
    )


SCENARIO = {
    "preview_function": "demo.RegisterPreview",
    "label": "Registration — dialog open",
    "keys": ["privacy_notice"],
}


def test_explicit_modal_excludes_closed_login_even_when_static_evidence_lists_both():
    settings = config([SCENARIO])
    catalog = extract_catalog(SOURCE, settings)
    assert all("privacy_notice" in preview.keys for preview in catalog.previews)
    choices = screen_scenarios(catalog, settings, "privacy_notice")
    assert [choice.preview_function for choice in choices] == ["demo.RegisterPreview"]
    assert choices[0].label == SCENARIO["label"] and choices[0].explicit
    assert len(screen_scenarios(catalog, settings, "email")) == 2
    assert screen_scenarios(catalog, CodeSourceConfig(), "email") == []


def test_multiple_explicit_states_preserve_reviewed_default_order_and_legacy_still_works():
    settings = config(
        [
            SCENARIO,
            {**SCENARIO, "preview_function": "demo.LoginPreview", "label": "Another open dialog"},
        ]
    )
    catalog = extract_catalog(SOURCE, settings)
    assert [choice.label for choice in screen_scenarios(catalog, settings, "privacy_notice")] == [
        "Registration — dialog open",
        "Another open dialog",
    ]
    legacy = screen_scenarios(catalog, config(), "privacy_notice")
    assert legacy[0].label == "Login" and not legacy[0].explicit


@pytest.mark.parametrize(
    "scenarios",
    [
        [SCENARIO, SCENARIO],
        [{**SCENARIO, "preview_function": "demo.NotRegistered"}],
        [{**SCENARIO, "label": "   "}],
        [{**SCENARIO, "keys": ["privacy_notice", "privacy_notice"]}],
        [{**SCENARIO, "keys": []}],
    ],
)
def test_scenario_configuration_rejects_invalid_or_unregistered_states(scenarios):
    with pytest.raises(ValidationError):
        config(scenarios)


def test_missing_key_or_preview_fails_import_validation():
    with pytest.raises(ValueError, match="keys are absent"):
        extract_catalog(SOURCE, config([{**SCENARIO, "keys": ["typo"]}]))
    with pytest.raises(ValueError, match="preview is absent"):
        extract_catalog(
            {"Empty.kt": b"fun text() = Res.strings.privacy_notice"}, config([SCENARIO])
        )
