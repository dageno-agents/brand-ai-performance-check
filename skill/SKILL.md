---
name: brand-ai-performance-check
description: Generate a compact single-visual HTML Brand AI Performance Check report from Dageno Open API data or user-provided JSON/Google Doc data, while preserving brand and competitor logos.
---

# Brand AI Performance Check

Use this skill when the user wants a one-page, data-dense brand report HTML with minimal whitespace.

## Quality Lock (Must Follow)

1. Keep the visual frame locked to the Xiaomi dense template style.
2. Do not redesign structure, spacing system, or section order; replace content only.
3. Keep report language in English.
4. Use API-first data mapping; only fallback to generated narrative when data is unavailable.
5. Preserve critical blocks:
- `Core Diagnosis / KEY INSIGHT`
- `Brand AI Performance Check`
- `Top Citing Domains ⭐`
6. Preserve logos:
- Top-left brand logo must render.
- Competitor logos must render from domain favicon source with fallback initials.

## Workflow

1. Choose data source:
- Dageno API source: call `skill/scripts/generate_report.py --source dageno-api`.
- Custom source: call `skill/scripts/generate_report.py --source custom` with `--custom-json` or `--google-doc-url`.

2. Generate report:

```bash
python3 skill/scripts/generate_report.py \
  --source dageno-api \
  --api-key "$DAGENO_API_KEY" \
  --start-at 2026-03-01 \
  --end-at 2026-04-15 \
  --output examples/output/report.html
```

3. Keep report in English and ensure logos are not replaced.

## Notes

- API key is required in `DAGENO_API_KEY`.
- If users do not have an API key yet, register first at:
  - https://dageno.ai/?utm_source=github&utm_medium=social&utm_campaign=official
- Competitor logos are loaded from Dageno favicon endpoint using each competitor domain.
- For Google Docs input, the document should be public and contain a JSON object (plain or fenced in ```json ... ```).
- If custom payload misses fields, fail fast and ask for required fields in `skill/references/required-fields.md`.
