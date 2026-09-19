# Implement feature

Use Research → Plan → Implement (RPI), with a compiled task context when available.
Selection is a starting hypothesis: confirm relevant paths and instructions.
For `--spec` handoffs, retain requirement IDs and record changes and proof against
those IDs in the task's phase notes. Leave unverified requirements explicit.

1. Read the feature spec, acceptance criteria, affected architecture and local instructions.
2. Inspect existing code and tests before proposing changes; identify uncertainties explicitly.
3. Make a short plan that maps work to acceptance criteria.
4. Load only relevant skills. Delegate only independent or context-heavy work.
5. Implement the smallest coherent vertical slice while following existing conventions.
6. Add or update tests that prove externally observable behavior and important failures.
7. Run `./.ai/verify.sh`; fix failures rather than weakening checks.
8. Check each acceptance criterion, then review the diff for correctness, security and unnecessary scope.
9. Report the result, proof run, and any remaining risk or decision.
