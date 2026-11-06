import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.localization.web.messages import WebMessageInvalid, validate_message


def test_parameters_allow_order_and_whitespace_but_preserve_dotted_identity():
    validate_message(
        "{{ name }}: {{value.requiredLength}}", "{{ value.requiredLength }} - {{name}}"
    )


@pytest.mark.parametrize(
    "target",
    [
        "Hello",
        "{{other}}",
        "{{name}} {{name}}",
        "{{name",
        "{{ name + 1 }}",
        "{{NAME}}",
        "{{ name }}<script>x</script>",
    ],
)
def test_invalid_parameters_or_injected_markup_are_rejected(target):
    with pytest.raises(WebMessageInvalid):
        validate_message("Hello {{name}}", target)


@pytest.mark.parametrize(
    "target",
    [
        '<a href="https://evil.test">Ciao {{name}}</a>',
        '<a href="mailto:team@example.test" onclick="x()">Ciao {{name}}</a>',
        '<a href="mailto:team@example.test">Ciao {{name}}',
        "<b>Ciao {{name}}</b>",
    ],
)
def test_rich_text_attributes_and_structure_are_protected(target):
    with pytest.raises(WebMessageInvalid):
        validate_message(
            '<a href="mailto:team@example.test">Hello {{name}}</a>', target, rich_text=True
        )


def test_rich_text_changes_only_prose():
    validate_message("<b>Hello</b><br> {{name}}", "<b>Ciao</b><br/> {{ name }}", rich_text=True)


@given(st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Zs")), max_size=100))
def test_plain_prose_can_change_without_changing_parameters(prose):
    validate_message("Hello {{item.name}}", prose + " {{item.name}}")
