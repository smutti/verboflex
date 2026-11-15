# Product names

Saving the name in **Product configuration → Product details** updates the current
product name immediately. The product list, workspace cards, workspace heading,
translation context and product search all use this same identity. A name change
does not require reimporting translations or publishing repository configuration.

The administrator-only save keeps the existing normalization, unique-name check,
optimistic version check and audit trail. The new name is reserved at save time.
Repository mappings, published revision snapshots, imports, translations and
proposals are not promoted by a rename. Configuration details still follow the
existing draft and publication flow; historical revisions retain their old name.

For drafts saved before this behavior was introduced, saving the existing name
again applies it to the current product. This requires the current draft version
and an available name. It does not increment the unchanged draft version or
invalidate its existing preview confirmation.

The product API regression suite covers immediate workspace discovery and search,
repeated renaming, duplicate-name prevention, concurrent saves, stale writes and
legacy-draft recovery. Tests use synthetic products and a disposable PostgreSQL
database.
