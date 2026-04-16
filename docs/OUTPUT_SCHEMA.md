# Output Schema (Normalized)

The renderer consumes a normalized object with these core blocks:

- `brand`
  - `name`, `domain`, `logo_url`, `generated_at`, `date_range`, `data_source`
- `headline`
  - `core_diagnosis`
- `overview`
  - `topic_count`, `prompt_count`, `ai_responses`, `platforms`, `languages`
- `kpis`
  - `overall_rank_snapshot`, `avg_position`, `sentiment`, `monthly_visits`, `avg_rank_gap`, `citation_gap`
- `metrics`
  - `visibility`, `sov`, `citation`, `sentiment` (each includes `you`, `comp`)
- `platform_compare[]`
  - `platform`, `visibility`, `sov`, `avg_rank`, `citation`, `sentiment`
- `topics[]`
- `high_value_prompts[]`
- `existing_strengths[]`
- `missing_trust_assets[]`
- `sentiment`
  - `positive`, `neutral`, `negative`, `score`
- `top_citing_domains[]`
  - `domain`, `monthly_visits`, `domain_type`, `count`, `citation_rate`
- `competitors[]`
  - `name`, `domain`, `logo_url`

For custom input fields, also see:
- `skill/references/required-fields.md`
