---
name: repo-onboarding
description: Review an existing repository and propose only evidence-backed changes to AI instructions and verification. Use when onboarding AI agents into a codebase or reviewing existing AGENTS.md.
---

# Repo onboarding (experiment)

Goal: identify repository-specific information that materially improves an agent's next code change. This is **not** a checklist for installing the kit or writing more documentation.

## 1. Establish the baseline (read-only)

- Read existing AGENTS.md, CLAUDE.md, Copilot instructions, CONTRIBUTING, README, relevant architecture docs, CI configuration and build/test entrypoints, where present.
- Trace at least one representative implementation path and its tests; inspect relevant modules and integration boundaries. Adapt depth to repository size. Do not dump file trees or infer conventions from filenames alone.
- Record only observed conventions with file paths and concrete examples. Separate explicit project policy, common but inconsistent practice, and assumptions.
- Determine whether current instructions already cover the observations. Follow higher-priority user and repository instructions.

## 2. Find high-value gaps

Consider a new instruction ONLY when it answers a decision the coding agent otherwise has to rediscover or often gets wrong, such as:

- An architectural boundary, module ownership rule or non-obvious integration contract.
- The correct test command, test fixture or prerequisite (verified against CI or scripts).
- An established pattern that differs from generic framework advice.
- A known failure mode documented by code, tests or decisions.

Do not add basic coding advice, language tutorials, speculative conventions, broad file inventories, or repeated content from existing docs. Prefer a link to authoritative documentation over copying it. Treat absence of evidence as a reason to omit a recommendation.

## 3. Propose, do not immediately write

For each proposed change, report:

- The current agent failure or avoidable rediscovery it addresses.
- Exact evidence (paths, symbols and relevant test/CI commands).
- The smallest instruction change and intended location.
- The downside: staleness, overconstraint, duplication or maintenance cost.

Rank proposals by likely practical impact. If nothing passes the bar, explicitly recommend **no change**. Prefer improving an existing file over creating a new file or installing additional skills. In particular, do not replace project-owned AGENTS.md or verify.sh.

Ask for approval before editing. Show a concise diff and scope, not a complete regenerated instruction bundle.

## 4. Apply and verify (only after approval)

- Change only approved files and preserve unrelated content.
- Check referenced paths and commands; run safe, relevant verification when feasible and report exactly what ran.
- Ensure instructions do not contradict each other or authoritative docs.
- Summarize the resulting behavioral guidance in a few sentences.

## 5. Evaluate whether this is useful

Before claiming improvement, compare with a baseline: give the same representative small repository task to an agent with existing instructions and an agent with the proposed changes (ideally separate sessions). Compare:

- Correct module/pattern chosen on first attempt.
- Relevant tests run successfully.
- Avoidable follow-up prompts, rework or incorrect assumptions.
- Extra instruction-maintenance cost.

If no meaningful improvement appears in at least two realistic tasks, recommend reverting or trimming the added instructions. Do not claim productivity gains from the existence of a generated file alone.
