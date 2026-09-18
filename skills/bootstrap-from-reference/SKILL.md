---
name: bootstrap-from-reference
description: Analyze an example repository and scaffold a separate new project from a requirements spec, preserving the reference tech stack, architecture, conventions and integration contracts. Use for starting any new application, service, library or tool from a reference implementation; also support analysis-only requests.
---

# Bootstrap from Reference

Turn a reference implementation into an evidence-based, runnable foundation for a new product. Default to scaffolding, not implementing the whole product. Keep the workflow portable across coding agents and stacks.

## Establish inputs and scope

Resolve the reference checkout or repository URL, destination, new project identity and requirements document from the request and available files. Read applicable repository instructions. If the reference is unavailable, request its URL or files; do not infer its stack from the domain. If the spec is absent, analyze the reference and prepare the reusable shell where possible, recording missing product decisions.

Use a separate destination; never modify the reference. Inspect existing destination files and local changes before writing. Preserve unrelated work and stop only the conflicting operation when overwriting would be necessary. Do not copy Git history or change existing remotes. A request to scaffold does not authorize publishing, deployment or CMS registration.

For analysis-only requests, report findings and a proposed reuse map without creating an app. Otherwise continue through implementation and verification without an unnecessary approval checkpoint. Ask only for decisions that block a correct result; record reversible assumptions and proceed with independent work.

## Derive the reference profile

Read manifests, lockfiles, runtime pins, compiler/bundler configuration, scripts, CI, entrypoints, representative modules, tests and deployment configuration. Trace one actual path from startup through UI/domain logic to external integration. Distinguish active code from stale examples and unused dependencies; do not treat README claims as proof of runtime behavior.

Record findings with source paths and relevant symbols/configuration keys, distinguishing **observed**, **inferred** and **unknown**. Capture:

- Runtime, language, framework, rendering engine, package manager and exact versions where available; distinguish manifest ranges from locked versions.
- Directory responsibilities, entrypoints, module boundaries, import aliases, naming, state/data flow, styling, assets, localization and testing conventions.
- Actual install, dev, build, lint, typecheck and non-watch test commands; output directory, base path and deployment assumptions.
- Environment variable names and purpose, external services, authentication, content/configuration loading and host contracts. Never record secret values.

Prefer executable configuration and traced behavior when documentation disagrees. Explain contradictions. Preserve the existing stack and dependency versions by default; do not modernize or substitute tooling just because it is familiar. When a defect blocks the new app, make the smallest necessary correction and record the deviation.

When the reference depends on external systems, shared packages or a host application, read [references/integration-boundaries.md](references/integration-boundaries.md).

## Map the requirements to the reference

Turn a short spec into concrete acceptance criteria without inventing product requirements. Map each requirement to existing reusable structure, a new extension point, or an unresolved decision.

Build a compact reuse map: source path/group → **keep**, **adapt**, **replace** or **omit**, with reason and destination. Separate framework/setup, shared presentation, integration adapters and domain-specific rules/content. Keep a recognizable folder organization; do not impose a preferred generic architecture.

Resolve explicit spec changes against compatibility constraints: a new domain requirement may replace business rules, but does not implicitly change an external API's schema. Flag genuine contradictions rather than quietly choosing one. Record both scaffold acceptance criteria and deferred full-product criteria so the two cannot be confused.

## Build the foundation

Selectively reuse files according to the map. Preserve appropriate licenses and attribution. Exclude credentials, real user data, dependency directories, caches, generated output and reference deployment identities. Inspect install/build hooks before executing them. Preserve environment examples using placeholder values only.

Retain the package manager and lockfile where compatible. If dependency or workspace metadata must change, update with that manager and inspect the resulting diff; do not fabricate lockfile entries. Identify workspace-only dependencies before extracting an app from a monorepo. Preserve shared packages or documented package references; do not claim an independently runnable repo while relative dependencies still point outside it.

Rename app/package identifiers, titles and app-owned metadata deliberately. Do not globally replace strings that also name stable SDK APIs, shared packages or host protocol fields. Preserve CI/build conventions, but remove or parameterize reference-specific deployment targets so a later push cannot deploy over the reference app.

Create the smallest usable foundation matching the new project's identity and reference structure, with extension points for its requirements. For an app/service this may be a runnable shell; for a library, CLI or other artifact, use its native build, usage example or execution path. Retain confirmed integration code; do not replace it with an invented SDK. Mark local fixtures/mocks clearly and keep them out of production paths. Leave full product features for later unless explicitly requested.

## Integrate with AI Dev Kit

If the kit is available, read its current README, CLI and generated configuration before using it. Follow project-owned specs and architecture over generic kit defaults. Use only supported detected stack skills; do not force an unsupported stack into the CLI's stack list.

The inspected v0.1.0 kit supports `aidev init <destination> --stacks ...` for a project harness, not application generation, and only copies named stack skills. Do not pass `bootstrap-from-reference` as a stack or claim init automatically installs this task skill. Keep the canonical skill at `skills/bootstrap-from-reference/` in the kit, or use the installed skill directly. If a project-local copy is useful, copy the entire skill directory, including references, to `.ai/skills/bootstrap-from-reference/` and reference it in project instructions.

Reuse and fill existing project documentation instead of generating duplicate documents. For this kit, put evidence, source identity (commit if available; otherwise archive/version or content fingerprint), reuse decisions and deviations in `architecture/reference-analysis.md`, the resulting architecture in `architecture/overview.md`, and the requirements with scaffold/full-product scope in `specs/features/<project>.md`.

Set `.ai/verify.sh` to the actual detected package manager and real checks, including build. The v0.1.0 generated frontend script uses npm and optional scripts; it is not sufficient evidence that another package manager's checks passed. Do not use silent missing-script success as verification. Keep normal project tooling usable without the kit.

## Verify and hand off

Run available deterministic checks and build; smoke-test the startup/render path when the runtime is available. Check aliases, assets, environment defaults, output/base paths and new identity. Search for old app identifiers and classify remaining occurrences; preserve legitimate provenance and contract names. Confirm reference files were not changed.

Distinguish local smoke tests, mocked contract tests and real external integration tests. A mock passing is not proof that the external system works. If private dependencies, host access or network availability prevent execution, report the exact unverified checks and prerequisite; do not weaken checks or swap the stack to produce green output.

Report what was created, inherited technology/structure, intentional deviations, actual verification results and remaining product/integration work. Give the concrete run/build/usage command appropriate to the project and next implementation slice. Do not call the full product finished when only its foundation exists.
