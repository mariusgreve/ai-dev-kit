# Testing principles

- Prove behavior at the cheapest reliable layer.
- Use integration tests at boundaries where mocks would hide meaningful behavior.
- Every bug fix should preserve its reproduction as a regression test when practical.
- Tests should assert outcomes, not incidental implementation details.
- A task is incomplete while required deterministic checks fail.
