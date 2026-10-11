"""Explicit plural profiles: CLDR cardinal categories and Qt Linguist form order.

Qt counts follow qttools 6.10 src/linguist/shared/numerus.cpp. Qt forms are
positional, not CLDR categories. Unknown Qt languages fail closed.
"""

from functools import lru_cache

from babel import Locale, UnknownLocaleError

ORDER = ("zero", "one", "two", "few", "many", "other")
QT_COUNTS = {
    1: "bi my zh dz fj gn hu id ja jv ko ms na om fa su tt th bo tr vi yo za",
    2: (
        "ab aa af sq am as ay az ba eu bn bg ca kw co da nl en eo et fo fi fur fy gl lg ka de "
        "el kl gu ha he hi ia ie it kn ks kk km rw ky ku lo la ln lb mg ml mr mn ne nso nb nn "
        "no oc or ps pt pa qu rm rn sn sd si so st es sw ss sv tg ta te to ts tn tk ug ur uz "
        "vo wo xh yi zu hy br fr fil ti wa is"
    ),
    3: "lv dv iu ik ga gv mi se sm sa sk cs mk lt bs be hr ru sr uk pl ro",
    4: "gd sl mt",
    5: "cy",
    6: "ar",
}


@lru_cache(maxsize=1024)
def plural_forms(format: str, language: str) -> tuple[tuple[str, str], ...]:
    if format == "android_xml":
        try:
            locale = Locale.parse(language, sep="-")
        except UnknownLocaleError, ValueError:
            raise ValueError("Plural rules unavailable for this language") from None
        tags = locale.plural_form.tags | {"other"}
        return tuple((tag, tag.capitalize()) for tag in ORDER if tag in tags)
    if format == "qt_ts":
        base = language.split("-")[0]
        count = next((n for n, codes in QT_COUNTS.items() if base in codes.split()), None)
        if count is None:
            raise ValueError("Qt plural rules unavailable for this language")
        labels = {
            1: ("All numbers",),
            2: ("Singular", "Plural"),
        }.get(count, tuple(f"Form {i + 1}" for i in range(count)))
        if base == "ar":
            labels = ("Zero", "One", "Two", "Few", "Many", "Other")
        elif base in {"ru", "uk", "be", "bs", "hr", "sr", "pl", "cs", "sk"}:
            labels = ("One", "Few", "Other")
        elif base == "lv":
            labels = ("Singular", "Plural", "Zero")
        return tuple((str(i), label) for i, label in enumerate(labels))
    raise ValueError("Plural authoring is unavailable for this format")
