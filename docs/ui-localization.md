# UI localization

VerboFlex bundles interface catalogs for English (`en`), Italian (`it`), German
(`de`), Spanish (`es`), French (`fr`) and Dutch (`nl`). The flag beside the profile
opens a menu with native language names and a checked selection. The same control
is available on the sign-in and profile pages and works with the keyboard.

On first visit, the application walks `navigator.languages`, matching regional
tags such as `fr-CA` to a supported base language. If none match, it uses English.
A manual selection is stored as `verboflex.ui-language` in local storage, takes
precedence over browser languages and synchronizes with other open tabs. It is a
browser preference, independent of the signed-in account. With storage blocked,
the current tab still changes language but cannot remember the choice on reload.

The interface updates without navigation or remounting forms, so drafts and open
filter dialogs survive. `html.lang` follows the selected language. The page keeps
`translate="no"`, `notranslate` and Google's no-translation meta directive to protect
repository and user content from automatic browser translation. Extensions that
ignore these directives may still alter the page.

## Content boundary

`frontend/src/i18n/locales/*.json` are flat UTF-8 catalogs with English source
phrases as keys. `t()` translates application labels, validation messages, help,
notifications and accessibility text. It preserves whitespace surrounding a key
and accepts named `{{placeholders}}` for values. React escapes the resulting text;
do not render translations as HTML. The catalogs are bundled with the application:
no runtime translation service receives UI text or user data.

Repository keys and paths, product and branch names, comments, translation values,
user input and API identifiers remain unchanged. A translation-content language
filter is independent of the interface language. Localize recognized status labels
only at display boundaries; never pass translated labels as API enum values or
compare them to API error messages. Dates, numbers and language names follow the
interface locale where formatted by the UI. Technical diagnostic codes retain
fallback text when no display label is defined.

## Adding copy

1. Use an English key with the complete message where possible. Interpolate data
   instead of passing user or repository values into `t()` as keys. Keep software
   terminology contextual: strings are text resources; commit and Compose are
   software terms, and branch identifiers such as `master` are data.
2. Add the same key and placeholder names to all six catalogs. For a count, provide
   complete singular and plural nouns; never append an English suffix to a
   translated word. English remains the fallback for unknown keys.
3. Subscribe the rendering component with `useUiLanguage()`. Module-level label
   maps use getters so they resolve at render time. Keep language changes out of
   data-fetch dependencies and component keys.
4. Run the catalog and behavior tests, then lint, typecheck and build. Changes to
   selection, persistence or rendering also require the focused browser test in
   [application checks](application-ci.md).

Catalog tests verify key parity, placeholders, selected domain terminology and
literal `t()` coverage. They reject translated values in comparisons and API state
fields. Component tests exercise storage failures, saved/browser preferences,
validation messages, preserved form values and Git branch names. Browser tests use
synthetic data for every locale, fallback, reload, cross-tab portal updates,
filter API values, keyboard selection and 320-pixel layouts.
