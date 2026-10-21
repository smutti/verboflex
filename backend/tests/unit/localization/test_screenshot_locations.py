"""No guessed coordinates: complete, unique, confident text matches only."""

import json
import struct
import subprocess
from pathlib import Path

import pytest

from tests.unit.localization.test_compose_capture import bundle, value
from verboflex.localization.code_keys import locations


def tsv(lines):
    result = [
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    ]
    for line, (text, y) in enumerate(lines, 1):
        left = 20
        for index, word in enumerate(text.split(), 1):
            width = len(word) * 7
            result.append(f"5\t1\t1\t1\t{line}\t{index}\t{left}\t{y}\t{width}\t14\t96\t{word}")
            left += width + 8
    return "\n".join(result)


def test_multiline_unicode_match_returns_normalized_line_rectangles():
    result = locations.match_text(
        tsv([("J’accepte la politique", 100), ("de confidentialité", 122)]),
        {"J'accepte la politique de confidentialité"},
        412,
        915,
    )
    assert result.status == "found" and len(result.regions) == 2
    assert result.regions[0].x == 20 / 412 and result.regions[0].y == 100 / 915
    assert result.regions[1].height == 14 / 915


def test_duplicate_text_is_ambiguous_and_partial_or_low_confidence_text_is_not_marked():
    assert (
        locations.match_text(
            tsv([("Save changes", 100), ("Save changes", 400)]), {"Save changes"}, 412, 915
        ).status
        == "ambiguous"
    )
    assert (
        locations.match_text(
            tsv([("Accept privacy", 100)]), {"Accept privacy policy"}, 412, 915
        ).status
        == "not_found"
    )
    assert (
        locations.match_text(
            tsv([("Accept privacy policy", 100)]).replace("\t96\t", "\t40\t"),
            {"Accept privacy policy"},
            412,
            915,
        ).status
        == "not_found"
    )
    assert locations.match_text(tsv([("Account", 100)]), {"Count"}, 412, 915).status == "not_found"
    assert (
        locations.match_text(
            tsv([("Save", 100), ("changes", 800)]), {"Save changes"}, 412, 915
        ).status
        == "not_found"
    )


@pytest.mark.parametrize(
    "data",
    [
        tsv([("Outside", 950)]),
        tsv([("Bad", 100)]).replace("\t96\t", "\tbroken\t"),
        "level\ttext\n5\tinvalid",
        "x" * (locations.MAX_TSV_BYTES + 1),
    ],
)
def test_invalid_or_unbounded_receipts_are_unavailable(data):
    assert locations.match_text(data, {"Outside"}, 412, 915).status == "unavailable"


def test_worker_matches_frozen_target_and_selected_locale_with_bounded_offline_process(monkeypatch):
    inputs = bundle([value("Welcome", "en"), value("Benvenuto")]).model_dump(mode="json")
    inputs["target_key"] = "title"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 412, 915)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 5 and kwargs["env"]["OMP_THREAD_LIMIT"] == "1"
        assert "-l" in command and "ita" in command
        assert Path(command[1]).read_bytes() == png
        kwargs["stdout"].write(tsv([("Benvenuto", 100)]).encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(locations.subprocess, "run", run)
    assert locations.locate_text(png, inputs).status == "found"
    assert len(calls) == 1
    # Older jobs and unsupported languages do not invoke OCR at all.
    assert locations.locate_text(png, {**inputs, "target_key": None}).status == "unavailable"
    assert locations.locate_text(png, {**inputs, "language": "ja"}).status == "unavailable"
    assert len(calls) == 1
    assert json.dumps(inputs).find("Benvenuto") > 0


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("ocr", 5)])
def test_missing_engine_or_timeout_does_not_fail_the_capture(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(locations.subprocess, "run", fail)
    inputs = bundle([value("Synthetic")]).model_dump(mode="json")
    inputs["target_key"] = "title"
    png = b"\x00" * 16 + struct.pack(">II", 412, 915)
    assert locations.locate_text(png, inputs).status == "unavailable"


def test_identical_text_under_another_key_cannot_be_attributed_to_this_key(monkeypatch):
    def must_not_run(*args, **kwargs):
        pytest.fail("Ambiguous keys must not invoke OCR")

    monkeypatch.setattr(locations.subprocess, "run", must_not_run)
    inputs = bundle([value("Save"), value("Save", key="other_control")]).model_dump(mode="json")
    inputs["target_key"] = "title"
    assert locations.locate_text(b"", inputs).status == "ambiguous"


def test_words_in_distant_columns_are_not_one_ui_label():
    data = tsv([("Privacy policy", 100)])
    lines = data.splitlines()
    fields = lines[-1].split("\t")
    fields[6] = "300"
    lines[-1] = "\t".join(fields)
    assert (
        locations.match_text("\n".join(lines), {"Privacy policy"}, 412, 915).status == "not_found"
    )
