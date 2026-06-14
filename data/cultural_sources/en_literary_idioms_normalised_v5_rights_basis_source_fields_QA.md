# English literary idioms normalised v5 QA

This v5 source file separates source locator text from quoted/contextual source
metadata and distinguishes licence status from rights basis.

## Schema changes checked

- Added optional `source_quote`, `source_note`, and `rights_basis` columns.
- Kept `source_location` for precise work/chapter/act/scene/verse locators.
- Moved short supporting quotation text out of `source_location` where supplied.
- Represented short common-use expressions with `source_license: not_required`
  and `rights_basis: common_usage_short_expression`.

## Rights/provenance review notes

- `common_usage_short_expression` is a rights basis, not a licence.
- Rows requiring explicit rights assessment should retain
  `source_license: copyright_or_rights_review_needed` until reviewed.
- Long source quotations should be avoided; use `source_note` for contextual
  prose that is not a source location.

## Import command

```powershell
python scripts/import_cultural_sources.py `
  --source data\cultural_sources\en_literary_idioms_normalised_v5_rights_basis_source_fields.csv `
  --out data\cultural_drafts\en_literary_idioms_normalised_v5.generated.yaml `
  --l10n-out backend\lesson\l10n\cultural_references\en.json
```
