# HTML email templates

Create a direct repository mapping and set its localization root to the folder
containing the email templates. Subfolders remain part of each template's identity;
the selected tree is one collection. Other folders in the repository are excluded.

HTML and HTM files must have a filename locale suffix, for example
`Welcome-EN.html`, `Welcome-IT.html`, or `reminders/Reminder-FR-BE.html`.
Underscore separators are also supported. The filename is authoritative; the
HTML `lang` attribute does not select the language. Confirm the source language
in the ordinary import preview.

## Editing and review

The importer exposes visible text fragments, including the document title and
text split by inline elements. It assigns internal identities from the relative
template name and structural address; it never inserts localization keys into HTML.
In Strings, choose **View template** beside a language to open its HTML context.
The translation detail page displays **HTML template preview** automatically in
the right-hand column used for screenshots, including for read-only viewers.
On narrow screens it follows the translation content. The email canvas scales to
fit the panel while keeping its original layout.

The selected body fragment is highlighted; document-title fragments appear above
the email. The preview uses the latest saved proposal for the selected fragment
and updates immediately with its unsaved text, without saving or generating a
screenshot. Other fragments show imported content, not their pending proposals.
Loading failures offer a retry without blocking the editor. Scripts, forms,
external styles and external images cannot load.
Inline styles remain visible, so the preview is useful for text context but is not
an email-client rendering certification.

Repository images in `<img src>` and legacy `background` attributes are collected
by the Celery import worker at the same commit as the template. `/images/logo.png`
is relative to the repository root; `../images/logo.png` is relative to the HTML
file, including folders outside the selected localization root. PNG, JPEG, GIF
and WebP images are embedded in the authorized preview as data URLs. The browser
never contacts the repository provider or receives its credentials. SVG files, remote
`src` URLs, source-provided `src` data URLs and paths escaping the repository are excluded.
CSS background images and `srcset` are not imported.

Existing projects need a source refresh to populate image snapshots. Missing,
unsupported or oversized images do not block text editing; missing local raster
images show an unavailable-images notice. Limits are 128 unique image reads and
8 MiB of image data per import, 512 KiB per image, and 1 MiB of embedded image
characters per rendered document. Image-only changes leave translation text,
proposals and revision identity intact; preview generation never writes repository
files. Migration
`0054_html_preview_images` stores this derived snapshot on the import execution;
its downgrade removes only the reproducible image cache.

Only text spans are writable. Tags, comments, attributes, links, styles and
surrounding whitespace remain byte-for-byte unchanged. Entered `<`, `>` and `&`
are encoded as text. Template variables such as `{{first_name}}` must retain their
exact spelling and count. Empty fragments and leading or trailing whitespace are
rejected to preserve structural identity. Translate split sentences together with
their surrounding text in mind; changing word order across tag boundaries requires
a template developer.

Imported text and spreadsheet-supplied text remain drafts. Existing review roles,
approval commits, branch history and explicit pull request creation still apply.
Configure a working branch different from the target branch and import from that
working branch. No HTML operation writes directly to the PR destination.

## Adding a language

With an approval branch configured, administrators and reviewers can use
**New HTML language** in the branch history view. Enter a normalized locale such
as `it` or `fr-BE`. The durable Celery job creates one corresponding file for every
source template, preserving directories, suffix separator and extension. It copies
source text initially: these are drafts to translate, not completed translations.
Once the commit completes, refresh the source to import the new files into Strings.

The authenticated `POST /api/v1/products/{product_id}/html-languages` endpoint also
accepts an optional bounded map of internal fragment keys to translations, for
controlled spreadsheet onboarding. Unknown keys or changed variables reject the
entire operation. Existing languages/files are never overwritten. A moved working
branch requires a source refresh before creation. Jobs share the ordinary serial
branch queue, recheck permissions before sending, and reconcile uncertain sends
without automatically resending a commit. An unsent failed language request can
be discarded from branch history; uncertain sends must be checked first. A PR is
still opened explicitly.

## Supported input and verification

Documents must be UTF-8, balanced HTML with an `html` element. The adapter supports
standard void elements, HTML entities, inline markup, styles and Outlook comments.
It excludes script/style bodies, comments and attributes from editable text.
Ambiguous language peers with different text addresses or variable placement fail
as a complete import. Template structure changes require a new import and review;
structural addresses are not a semantic match across arbitrary template rewrites.

Existing discovery, file-size and aggregate bounds remain in force. HTML indexing
additionally caps depth at 64, tags at 20,000 and text fragments at 5,000 per file.
Migration `0053_html_format` expands the closed format, branch-job and audit action
constraints. Its downgrade refuses to discard HTML rows or job/audit history.

Synthetic tests cover filename locales, nested collections, preserved bytes and
entities, variable guards, malformed documents, API permissions, import-to-editor
projections and durable language creation without automatic PR publication.
