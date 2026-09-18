---
name: java
description: Implement or review Java code, including API design, concurrency, testing and maintainable language-level choices.
---

# Java

Inspect the project's Java version, build tool and conventions before changing code.

- Prefer clear types and immutable values; use records when their value semantics fit.
- Model absence explicitly. Do not use `Optional` for fields or parameters without a project-specific reason.
- Preserve exception causes and translate exceptions only at meaningful boundaries.
- Use structured concurrency or executors already established by the project; never introduce unbounded concurrency silently.
- Add focused unit tests and run the repository verification entrypoint.
