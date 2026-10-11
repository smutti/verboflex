import pytest

from verboflex.localization.placeholders import compatible_arguments


@pytest.mark.parametrize(
    "source,target,format,compatible",
    [
        ("%n items in %1", "%1: %n elementi", "qt_ts", True),
        ("%Ln items", "%n elementi", "qt_ts", False),
        ("%s has %d", "%2$d per %1$s", "android_xml", True),
        ("%*.*f", "%f", "ios_strings", False),
        ("%*.*f", "%3$*1$.*2$f", "ios_strings", True),
        ("%lld", "%d", "ios_strings", False),
        ("Hi {name}", "Ciao {name}", "json", True),
        ("Hi {name}", "Ciao", "json", False),
        ("{n, plural, one {item} other {items}}", "items", "json", False),
        ("Hello {{name}}", "Ciao", "json", False),
    ],
)
def test_argument_contract(source, target, format, compatible):
    assert compatible_arguments(source, target, format) is compatible
