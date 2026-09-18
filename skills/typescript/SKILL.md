---
name: typescript
description: Implement or review strict TypeScript types, domain models, API boundaries and safe narrowing.
---

# TypeScript

- Preserve strictness; avoid `any` and unsafe assertions unless the boundary is documented and validated.
- Model variants with discriminated unions and make exhaustive handling visible.
- Treat network, storage and user input as `unknown` until validated.
- Prefer inference inside implementations and explicit types at public boundaries.
- Keep runtime validation distinct from compile-time typing.
