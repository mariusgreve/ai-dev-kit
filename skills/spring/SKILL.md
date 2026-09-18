---
name: spring
description: Implement or review Spring Boot application changes involving web APIs, services, transactions, persistence or integration tests.
---

# Spring

Read the project architecture and inspect its existing Spring conventions first.

- Prefer constructor injection and explicit dependencies.
- Put transaction boundaries around cohesive service operations; account for proxy boundaries and self-invocation.
- Keep API contracts separate from persistence entities unless the project explicitly chooses otherwise.
- Validate requests at the boundary and centralize consistent error translation.
- Use slice tests for narrow framework behavior and integration tests, often with Testcontainers, where real infrastructure semantics matter.
- Run the project's verification entrypoint before completion.
