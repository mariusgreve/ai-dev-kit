# Working in this repository

Follow the user's task and this project's existing code, documentation and conventions.
Load relevant skills from `.ai/skills/` when they help with the task.

- Inspect the affected code and tests before editing. Search for callers and related behavior as needed.
- Keep changes focused. For a small task, work directly; for a larger change, make a short plan first.
- Use a spec or decision note when scope or a durable trade-off needs clarification. Do not create process documents for routine changes.
- For bugs, establish a reproduction and add a regression test when practical.
- Test observable behavior and important failures. Keep checks proportional to the change.
- For reviews, inspect the diff and affected paths; prioritize correctness, security and missing tests over style.
- Preserve unrelated work and follow existing architecture. Add abstractions only when the current task needs them.
- Validate input and authorization at system boundaries; keep secrets out of code, logs and documentation.
- Run `./.ai/verify.sh` before reporting completion. If it does not match the actual build, update it using the project's real commands.
- Report the change, checks actually run and any remaining limitations. A passing command alone does not prove every requirement.
