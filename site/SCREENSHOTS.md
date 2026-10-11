# Application screenshots

Captured on 2026-10-11 from the running VerboFlex portal after First release
(1e20e10). Images are unretouched browser captures at the normal 1280px viewport;
full-page captures include all language rows. Only the synthetic public
[Northstar demo](https://github.com/smutti/verboflex-demo) products are visible.
No proposals were saved, approved or submitted to take these images.
The New key example was filled and discarded.

| Image | Capture | SHA-256 |
| --- | --- | --- |
| `products.jpg` | Product workspace searched for Northstar; all four cards. | `fc8fd581b8f83c8f81d5a55c01ad26f47f095c8e9995660b928d438bdcec565d` |
| `multilingual.jpg` | Android welcome_title, four supported language rows. | `1aee9bcca4201ca052eea54b7087e8ecdbc82464dc6b71d03d5929092411949f` |
| `missing.jpg` | Android empty_search with Needs translation filter. | `8a95e9b9c48f4ff33855b4baab56bc6091455119c3759308b87b410d9483fc73` |
| `new-key.jpg` | Unsaved Italian onboarding_tip in an existing Android XML file. | `90edf3ab612e85e80868e2da90eddfc5b4f53a8b7a8d88c385d939b9e3aa9a7f` |
| `plurals.jpg` | Android files_selected, Italian native plural forms expanded. | `cdfd92a853348c996e26c5b423c74ddd6146653656bd79df3e6db34988f2c285` |
| `reuse.jpg` | Android save_profile_changes, Italian editor and source similarity suggestion. | `f77a0d4f9312edbe29141b74d88f355c166403c92179658ae0c5459174f6d65b` |
| `filters.jpg` | Filter dialog with Needs translation selected. | `960d3fff7d74a8cbc691918ce3cf7eb17fc61af7e5a6597c3c0feace9fad35ad` |

## Updating the gallery

1. Use only synthetic products. Filter the product list before capturing it.
2. Wait for actual rows, suggestions and forms to finish loading. Capture the
   current browser UI; do not fabricate API responses or edit the DOM for images.
3. Inspect every image for account details, private names, loading skeletons and
   clipped controls. Cancel any unsaved form used for the illustration.
4. Update dimensions, alt text and captions in `content.py`, and the hashes here.
   Add new filenames explicitly; the build never copies the whole asset directory.
5. Run `python3 site/build.py` and `python3 site/check.py`; verify desktop and mobile
   views. CI also checks real image loading and full-size navigation.

Images load lazily and link to their full-size originals. Each JPEG is limited to
250 KB and the complete site to 1.5 MB. The interactive sample has its own invented
data; its totals do not describe the Northstar screenshots.
