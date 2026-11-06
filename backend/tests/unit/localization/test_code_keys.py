"""Synthetic fixtures for code-only localization sources."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.localization.code_keys.catalog import CodeSourceConfig, extract_catalog
from verboflex.localization.code_keys.process import extract_catalog_isolated


def test_isolated_catalog_includes_all_modules_at_source_file_limit() -> None:
    files = {
        f"{'app' if index < 500 else 'shared'}/src/main/Screen{index}.kt": (
            f"fun screen{index}() = Res.strings.title_{index}\n".encode()
        )
        for index in range(5_000)
    }
    catalog = extract_catalog_isolated(files, CodeSourceConfig())
    assert set(catalog.keys) == {f"title_{index}" for index in range(5_000)}
    assert {occurrence.path for occurrence in catalog.occurrences} == set(files)


@pytest.mark.parametrize("extract", [extract_catalog, extract_catalog_isolated])
def test_oversized_code_catalog_is_rejected_before_parsing(extract) -> None:
    files = {f"Screen{index}.kt": b"invalid Kotlin" for index in range(5_001)}
    with pytest.raises(ValueError, match="Code source budget exceeded"):
        extract(files, CodeSourceConfig())


@pytest.mark.parametrize(
    "extension,source",
    [
        ("kt", b'enum class Keys(val key: String) { TITLE("title"), HELP("help"); }'),
        ("java", b'enum Keys { TITLE("title"), HELP("help"); Keys(String key) {} }'),
    ],
)
def test_explicit_enum_string_values(extension, source) -> None:
    catalog = extract_catalog(
        {f"Keys.{extension}": source}, CodeSourceConfig(declaration_symbols=("Keys.*",))
    )
    assert catalog.keys == ("help", "title")


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=48))
def test_comments_and_strings_cannot_add_resource_keys(name: str) -> None:
    source = f'// Res.strings.{name}\nval ignored = "Res.strings.{name}"\n'.encode()
    assert extract_catalog({"Code.kt": source}, CodeSourceConfig()).keys == ()


def test_overloads_preserve_conservative_preview_evidence() -> None:
    catalog = extract_catalog(
        {
            "Screen.kt": b"""package demo
fun Screen() { Screen(true) }
fun Screen(ready: Boolean) = Res.strings.title
@Preview @Composable fun Example() { Screen() }
"""
        },
        CodeSourceConfig(),
    )
    assert catalog.previews[0].keys == ("title",)


def test_kotlin_resource_references_and_preview_calls() -> None:
    source = b"""package demo
import demo.resources.Res as Words
@Composable
fun LoginScreen() {
 Text(stringResource(Words.strings.login_title.resourceId))
 Text("Res.strings.not_a_key")
 // Words.strings.comment
 Words.strings.untranslated("temporary")
}
@Preview(name = "Login")
@Composable
private fun LoginPreview() {
 LoginScreen()
}
"""
    catalog = extract_catalog(
        {"app/src/main/Login.kt": source},
        CodeSourceConfig(resource_roots=("demo.resources.Res.strings",)),
    )
    assert catalog.keys == ("login_title",)
    assert catalog.occurrences[0].line == 5
    assert catalog.previews[0].function == "demo.LoginPreview"
    assert catalog.previews[0].keys == ("login_title",)
    assert catalog.previews[0].evidence == "static_reference"


def test_java_moko_getters_and_plain_field_references() -> None:
    catalog = extract_catalog(
        {
            "src/main/Screen.java": b"""package demo;
import demo.resources.Res;
class Screen {
 void show() { localize(Res.strings.INSTANCE.getLogin_title());
   localize(Res.strings.cancel); }
}"""
        },
        CodeSourceConfig(resource_roots=("demo.resources.Res.strings",)),
    )
    assert catalog.keys == ("cancel", "login_title")


@pytest.mark.parametrize("modifier", ["private", "internal", "public", "protected"])
def test_annotated_visibility_function_with_nested_lambda_preserves_evidence(modifier) -> None:
    source = f'''package demo
// Synthetic accented text: caffè; private fun Ignored() = Res.strings.comment
val ignored = "private fun Hidden() = Res.strings.string_literal"
@Preview(name = "Light", showBackground = true)
@Preview(name = "Dark", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
{modifier} fun AccountPreview() {{
  Theme {{
    AccountContent(state = AccountState(),)
  }}
}}
@Composable
private fun AccountContent(state: AccountState) {{
  Text(Res.strings.account_title)
}}
'''.encode()
    catalog = extract_catalog({"Screen.kt": source}, CodeSourceConfig())
    assert catalog.keys == ("account_title",)
    assert len(catalog.previews) == 2
    assert all(preview.function == "demo.AccountPreview" for preview in catalog.previews)
    assert all(preview.keys == ("account_title",) for preview in catalog.previews)
    assert all(preview.line == 4 for preview in catalog.previews)
    assert catalog.occurrences[0].function == "demo.AccountContent"
    assert catalog.occurrences[0].line == 14
    assert catalog.occurrences[0].column == 8


def test_incomplete_visibility_function_is_rejected() -> None:
    with pytest.raises(ValueError, match="Incomplete code syntax"):
        extract_catalog(
            {"Screen.kt": b"@Preview\nprivate fun Broken() { Theme { Res.strings.title\n"},
            CodeSourceConfig(),
        )


def test_selected_constants_and_configured_calls() -> None:
    catalog = extract_catalog(
        {
            "Keys.kt": b"""package demo
object Keys {
 const val TITLE = "login.title"
 const val HELP = TITLE + ".help"
 const val OTHER = "not_selected"
}
fun screen() {
 translate("login.cancel")
}
"""
        },
        CodeSourceConfig(
            declaration_symbols=("demo.Keys.TITLE", "demo.Keys.HELP"),
            localization_calls=("translate",),
        ),
    )
    assert catalog.keys == ("login.cancel", "login.title", "login.title.help")


def test_java_qualified_localization_call_retains_receiver() -> None:
    catalog = extract_catalog(
        {
            "Screen.java": b"""package demo;
import demo.i18n.Translator;
class Screen {
 void show() { Translator.text("title"); Other.text("unrelated"); }
}"""
        },
        CodeSourceConfig(localization_calls=("demo.i18n.Translator.text",)),
    )
    assert catalog.keys == ("title",)
    assert catalog.occurrences[0].function == "demo.Screen.show"


@pytest.mark.parametrize(
    "source",
    [
        b"object Keys {\n const val TITLE = dynamic()\n}\n",
        b'object Keys {\n const val TITLE = "key.${value}"\n}\n',
        b"object Keys {\n const val TITLE = OTHER\n const val OTHER = TITLE\n}\n",
        b"fun broken( { Res.strings.title\n",
    ],
)
def test_incomplete_or_dynamic_extraction_is_rejected(source: bytes) -> None:
    with pytest.raises(ValueError):
        extract_catalog({"Keys.kt": source}, CodeSourceConfig(declaration_symbols=("Keys.TITLE",)))


def test_rejects_duplicate_declarations_and_unsafe_paths() -> None:
    with pytest.raises(ValueError):
        extract_catalog(
            {
                "Keys.java": b'class Keys { static final String A = "same"; '
                b'static final String B = "same"; }'
            },
            CodeSourceConfig(declaration_symbols=("Keys.*",)),
        )
    with pytest.raises(ValueError):
        extract_catalog({"../Keys.kt": b""}, CodeSourceConfig())


def test_test_and_build_sources_are_excluded() -> None:
    catalog = extract_catalog(
        {
            "src/test/Example.kt": b"broken",
            "build/Generated.kt": b"broken",
            "src/main/Example.kt": b"fun screen() = Res.strings.title\n",
        },
        CodeSourceConfig(),
    )
    assert catalog.keys == ("title",)


def test_unrelated_extension_import_overloads_do_not_block_resource_index() -> None:
    catalog = extract_catalog(
        {
            "Screen.kt": b"""import demo.one.getValue
import demo.two.getValue
import demo.resources.Res
fun screen() = Res.strings.title
"""
        },
        CodeSourceConfig(resource_roots=("demo.resources.Res.strings",)),
    )
    assert catalog.keys == ("title",)
