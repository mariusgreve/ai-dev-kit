# Preserve integration boundaries

Use this reference only for dependencies across the project boundary. Derive the architecture from the source; do not assume a web app, backend, database, host application or deployment model.

## Inspect the actual contract

Trace callers and adapters, then record the applicable facts with source evidence:

| Boundary | Relevant evidence |
| --- | --- |
| API or SDK | Protocol, package/version, request/response schemas, authentication configuration, error behavior |
| Events or host bridge | Event names, direction, payloads, initialization, lifecycle and cleanup |
| Persistence | Schema/migrations, ownership, connection configuration and seed-data requirements |
| Shared packages | Published vs workspace dependency, generated code, build order and availability outside the source tree |
| Files or pipelines | Formats, paths, encoding, input/output schema and invocation contract |
| Runtime/deployment | Required services, environment variable names, ports, artifacts and target identifiers |

These are inspection prompts, not requirements to add new systems. Mark undocumented contracts as unknown. Keep project-owned identity separate from public names, wire formats and shared-package identifiers that must remain stable.

## Extract without breaking compatibility

Preserve required adapters and contract types while removing reference-specific domain behavior. Classify assets, seed data and fixtures by purpose before removing them: some illustrate the old product; others make the shared contract executable.

Expose per-project settings without copying credentials, production endpoints that cause writes, deployment identities or real user data. Do not invent replacement SDKs or services to hide missing access. Identify workspace-relative imports, local packages, submodules and generated artifacts that prevent independent use; resolve them using the reference's supported mechanisms or report the blocker.

Keep test doubles development-only and based on observed contracts. If the contract is unknown, document the gap rather than producing a fictional production implementation.

## Verify at the right level

Choose checks appropriate to the artifact: library import/public API, CLI invocation/exit behavior, service startup/request, UI launch, or pipeline input/output. Reuse existing test infrastructure. Test retained boundary behavior when it can break during extraction or renaming.

Separate local behavior, mocked contracts and actual external integration. State which checks require credentials, private packages, infrastructure or another application. Report unavailable checks honestly without weakening them or silently replacing the stack.
