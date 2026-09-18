# Claude Code

Read and follow `AGENTS.md`. Reusable project skills are under `.ai/skills/` and
workflows under `.ai/playbooks/`. Load only those relevant to the current task.
Use subagents only for independent parallel work, context isolation, or genuine
specialization. The completion gate is `./.ai/verify.sh` plus the active spec's
acceptance criteria.
