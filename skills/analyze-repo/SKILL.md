---
name: analyze-repo
description: Quickly understand an unfamiliar repository and identify where to start reading.
---

# Analyze repository

Help a developer quickly understand an unfamiliar repository.

The goal is onboarding, not exhaustive architecture analysis. Focus on the smallest amount of information needed to understand what the repository does, how it is structured, and where to start reading.

## Instructions

Analyze the repository using the following steps.

### 1. Understand what the repository is

Read the most relevant top-level documentation and configuration files first.

Determine:

- what the repository appears to do
- whether it is an application, service, library, frontend, infrastructure repo, monorepo, etc.
- the primary language(s)
- the main framework(s)
- the build/package tooling
- important runtime or infrastructure dependencies

Do not list every dependency. Mention only the ones that help explain the system.

### 2. Understand the structure

Inspect the repository tree and explain the important directories or modules.

Focus on directories that contain:

- application entry points
- API/routes/controllers
- business or domain logic
- persistence/data access
- external integrations
- configuration
- tests

Ignore generated files, vendored dependencies, build output, and other noise unless they are important to understanding the repository.

### 3. Find the entry points

Identify the files a developer should look at first.

Examples include:

- application bootstrap/main
- primary route/controller definitions
- representative services/use cases
- persistence boundaries
- important configuration
- representative tests

Prefer concrete file paths over abstract descriptions.

### 4. Trace one representative flow

Find one useful, representative flow through the system.

For example:

HTTP request
→ controller
→ service/use case
→ repository/client
→ database/external system

For a frontend this might instead be:

route/page
→ component
→ state/data fetching
→ API

For another type of repository, choose an equivalent flow that best explains how the system works.

Keep this concise. Do not attempt to trace every flow.

### 5. Identify useful conventions

Point out a few conventions that would help a new developer work in the repository, such as:

- where business logic normally lives
- how dependencies are wired
- how persistence is handled
- how tests are structured
- naming or packaging conventions
- how configuration is managed

Only state conventions that are clearly supported by the repository.

### 6. Identify AI conventions

Check whether the repository defines conventions or instructions for AI-assisted development.

Look for files and directories such as:

- AGENTS.md
- CLAUDE.md
- .github/copilot-instructions.md
- .cursor/
- .windsurf/
- .claude/
- skills/
- prompts/
- playbooks/
- spec or planning directories
- repository-specific agent or AI configuration

Summarize:

- which AI tools or agents the repository appears to support
- where the main AI instructions live
- important rules or constraints agents are expected to follow
- whether there is a defined workflow such as spec → plan → implement → review
- any project-specific skills, prompts, or reusable agent instructions worth knowing about

Do not infer AI conventions purely from normal source-code patterns. Only report conventions that are explicitly represented in repository files or configuration.

### 7. Recommend a reading order

Give a short, concrete sequence of files to read next.

Aim for roughly 5–10 files or directories.

The reading order should help the developer go from:

overview
→ entry point
→ representative feature
→ persistence/integration
→ tests

## Output

Use this structure:

# Repository overview

## What this is

A short explanation of what the repository appears to do.

## Stack

Only the important technologies needed to understand the project.

## Structure

Explain the important directories/modules and what they contain.

## Typical flow

Show one representative flow through the system, using concrete file or type names where possible.

## Important files

List the most useful files for understanding the repository, with a short explanation of each.

## Things worth knowing

List a small number of useful conventions or observations.

## AI conventions

Summarize any repository-specific AI instructions, agent configuration, supported AI tools, or AI development workflow.

Omit this section if the repository contains no meaningful AI-specific conventions.

## Suggested reading order

Give a numbered list of the files or directories that should be read next.

## Questions / uncertainties

Only include this section when something material is unclear from the repository.

Clearly distinguish uncertainty from fact.

## Guidelines

- Be concise.
- Optimize for helping a developer become productive quickly.
- Prefer concrete file paths and examples over general explanations.
- Do not produce an exhaustive architecture analysis.
- Do not document every module, dependency, class, or endpoint.
- Do not create architecture diagrams unless they materially improve understanding.
- Do not assign architecture, quality, complexity, or technical-debt scores.
- Do not speculate when the repository does not provide enough evidence.
- If the repository is large, sample representative areas instead of trying to analyze everything.
- Prefer existing representative implementations over theoretical recommendations.
- Do not suggest refactors or improvements unless explicitly asked.
- Do not modify any files.
