# Fix bug

1. Restate the observed and expected behavior; capture a minimal reproduction.
2. Inspect evidence and trace the failing path. Do not edit until there is a testable hypothesis.
3. Add a failing regression test when practical.
4. Make the narrowest root-cause fix; avoid unrelated cleanup.
5. Run focused tests, then `./.ai/verify.sh`.
6. Review adjacent failure modes and report cause, fix and proof.
