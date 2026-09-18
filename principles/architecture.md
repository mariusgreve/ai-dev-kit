# Architecture principles

- Prefer explicit module boundaries and one-way dependencies.
- Keep framework and transport concerns away from domain rules where the separation pays for itself.
- Follow the repository's established design unless the task explicitly changes it.
- Record consequential, durable decisions as ADRs; do not use ADRs for routine implementation details.
- Optimize first for clarity and changeability, then introduce distribution or abstraction when evidence justifies it.
