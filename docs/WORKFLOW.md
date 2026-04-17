# Workflow

## End-to-End Pipeline

```mermaid
flowchart TD
    A[Input Mode Selection] --> B{Source Type}
    B -->|Dageno API| C[Fetch Brand / Topics / Prompts / Citations / GEO Analysis]
    B -->|Custom JSON| D[Load & Validate Custom JSON]
    B -->|Google Doc| E[Export Text from Public Google Doc]
    E --> F[Extract JSON Object]
    C --> G[Normalize Data Model]
    D --> G
    F --> G
    G --> H[Apply Stable Dense Template Mapping]
    H --> I[Render Dense Landscape HTML]
    I --> J[Logo Safety Check]
    J --> K[Output HTML + Optional Normalized JSON]
```

## Data Priority Rule

1. Use Dageno API fields whenever available.
2. If critical fields are missing, fallback to generated narrative text (for example Core Diagnosis).
3. Never break template layout to fit missing data.

## Language Rule

- Output report language must be English.
