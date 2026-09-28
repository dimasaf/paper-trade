# Domain Docs

How the engineering skills should consume this repository's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repository root.
- **`docs/adr/`**: read ADRs that touch the area about to be changed.

If one of these files does not exist, proceed silently. The `/domain-modeling` skill creates them lazily when terms or decisions are resolved.

## File structure

This is a single-context repository:

```text
/
├── CONTEXT.md
├── docs/adr/
└── apps/
```

If the repository later gains genuinely separate bounded contexts, replace this layout with a root `CONTEXT-MAP.md` pointing to the relevant per-context glossaries and ADR directories.

## Use the glossary's vocabulary

When output names a domain concept — in an issue title, refactor proposal, hypothesis, or test — use the canonical term from `CONTEXT.md`. Do not drift to synonyms the glossary explicitly avoids.

If a needed concept is missing, reconsider whether it belongs to the domain. If it does, capture it through `/domain-modeling` rather than inventing local vocabulary.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
