# Required Custom Data Fields

If using `--source custom`, provide a JSON object with these fields:

- `brand`: object
  - `name` string
  - `domain` string
  - `logo_url` string (recommended)
  - `generated_at` string (YYYY-MM-DD)
  - `date_range` string
- `headline`: object
  - `core_diagnosis` string
  - `key_insight` string
- `kpis`: object
  - `avg_rank_lead` string
  - `seo_bounce` string
  - `overall_rank_snapshot` string
  - `avg_position` string
  - `sentiment` string
  - `monthly_visits` string
- `competitors`: array of objects
  - `name` string
  - `domain` string
  - `logo_url` string (recommended)
- `competitor_summary`: string
- `platform_compare`: array of objects
  - `platform`, `visibility`, `sov`, `avg_rank`, `citation`, `sentiment`
- `topics`: array of strings
- `high_value_prompts`: array of strings
- `existing_strengths`: array of strings
- `missing_trust_assets`: array of strings
- `sentiment`: object
  - `positive` number
  - `neutral` number
  - `negative` number
  - `score` string/number
  - `positive_keywords` array of strings
  - `negative_keywords` array of strings
- `top_citing_domains`: array of objects
  - `domain`, `monthly_visits`, `domain_type`, `count`, `citation_rate`

## Google Doc Input

Place the same JSON into a public Google Doc. The script exports text and extracts JSON automatically.
