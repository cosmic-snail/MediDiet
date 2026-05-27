# Repository Agent Notes

## Naming

- Use variable names that describe the domain object they carry. Prefer `source_content_strategy`, `observation_record`, or `gold_evaluation_row` over generic names such as `variant`, `run`, or `row` when the domain meaning matters.
- Preserve external schema field names for compatibility, but keep local variables explicit even when serialized fields are shorter.

## Finite Strategies

- Represent closed sets of strategy identifiers with enums or centralized constants, then normalize user input at module boundaries.
- Avoid scattering ad hoc string comparisons for modes such as source-content selection, comparator arms, or experiment ids.
