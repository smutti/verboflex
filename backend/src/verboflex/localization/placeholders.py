"""Conservative argument compatibility for suggestions; never rewrite syntax."""

import re
from collections import Counter

_PRINTF = re.compile(
    r"%(?:(\d+)\$)?[-+#0 ']*(\d+|\*(?:\d+\$)?)?"
    r"(?:\.(\d+|\*(?:\d+\$)?))?([hlLjzt]*)([diouxXeEfFgGaAcCsSpn@])"
)
_QT = re.compile(r"%L?(?:n|[1-9][0-9]?)")
_BRACES = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_.]*|\d+)\}(?!\})")
_COMPLEX = re.compile(r"\{[^{}]*[,{]|\{\{")


def argument_contract(text: str, format: str) -> tuple[tuple[str, int], ...]:
    text = text.replace("%%", "")
    if format == "qt_ts":
        tokens = _QT.findall(text)
    else:
        position = 0
        tokens = []
        for match in _PRINTF.finditer(text):
            for width in (match[2], match[3]):
                if width and width.startswith("*"):
                    explicit = width[1:].rstrip("$")
                    if not explicit:
                        position += 1
                    tokens.append(f"printf:{explicit or position}:int")
            if not match[1]:
                position += 1
            tokens.append(f"printf:{match[1] or position}:{match[4]}{match[5]}")
        tokens.extend(f"brace:{name}" for name in _BRACES.findall(text))
    return tuple(sorted(Counter(tokens).items()))


def compatible_arguments(source: str, target: str, format: str) -> bool:
    # ICU / nested interpolation requires its own parser and runtime profile.
    # Decline these suggestions instead of treating unrecognized arguments as empty.
    if format != "qt_ts" and (_COMPLEX.search(source) or _COMPLEX.search(target)):
        return False
    return argument_contract(source, format) == argument_contract(target, format)
