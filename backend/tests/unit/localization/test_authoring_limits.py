from uuid import uuid4

import pytest
from pydantic import ValidationError

from verboflex.schemas.authoring import AuthoringInput


def test_multibyte_payload_is_bounded_before_database_write():
    with pytest.raises(ValidationError, match="too large"):
        AuthoringInput(
            scope_id=uuid4(),
            execution_id=uuid4(),
            file_position=0,
            key="test",
            language="ar",
            kind="plural",
            forms=[
                {"form": f, "text": "😀" * 65536}
                for f in ["zero", "one", "two", "few", "many", "other"]
            ],
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("key", "a\x00b"),
        ("source_text", "\ud800"),
        ("parents", ["a\x00b"]),
        ("file_position", True),
        ("expected_version", True),
    ],
)
def test_invalid_authoring_input_cannot_reach_database(field, value):
    body = dict(
        scope_id=uuid4(),
        execution_id=uuid4(),
        file_position=0,
        key="test",
        language="en",
        forms=[{"text": "Hello"}],
    )
    body[field] = value
    with pytest.raises(ValidationError):
        AuthoringInput.model_validate(body)
