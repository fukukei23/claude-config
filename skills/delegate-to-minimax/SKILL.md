---
name: delegate-to-minimax
description: Route bulk text processing tasks to MiniMax MCP tools to conserve GLM rate limits. Use this skill whenever the user asks for summarization, format conversion, test data generation, email drafts, commit messages, keyword extraction, data cleaning, boilerplate code generation, or document drafting. Also trigger when processing large volumes of files or content. Do NOT use for translation (MiniMax mixes Chinese into Japanese), code changes to existing codebases, architecture design, debugging, code review, or security decisions — those stay with GLM.
---

# MiniMax Task Delegation

Route text-heavy, non-critical tasks to MiniMax MCP tools to conserve GLM (ZAI API) rate limits. MiniMax is free and abundant — use it aggressively for bulk work.

## Routing Table

### Delegate to MiniMax (use specific MCP tool)

| Task | MCP Tool |
|---|---|
| File/URL content summarization | `minimax_summarize_file` or `minimax_ask` |
| Format conversion (JSON↔YAML↔CSV↔XML↔TOML) | `minimax_convert_format` |
| Test data / mock data generation | `minimax_generate_test_data` |
| Business email drafting | `minimax_write_email` |
| Commit message generation | `glm_git_commit_message` (GLM, but lightweight) |
| CHANGELOG generation | `glm_generate_changelog` (GLM, but lightweight) |
| Keyword / key point extraction | `minimax_extract_keywords` |
| Bulk file processing (2+ files) | `minimax_batch_process` |
| Data cleaning / normalization | `minimax_clean_data` |
| Boilerplate / template code generation | `minimax_generate_code` |
| Document drafting (README, CLAUDE.md drafts) | `minimax_write_document` or `glm_write_document` |
| Code generation (standalone, no existing deps) | `minimax_generate_code` |
| Regex generation / explanation | `glm_generate_regex` |
| Cron expression generation | `minimax_cron_helper` |
| Diff summary (git diff) | `minimax_diff_summary` |
| Schema generation from sample data | `minimax_generate_schema` |
| Env/config validation | `minimax_env_check` |
| Error log grouping | `minimax_error_group` |
| Log analysis | `minimax_log_analysis` |

### Keep on GLM (do NOT delegate)

| Task | Reason |
|---|---|
| Translation (any language pair) | MiniMax mixes Chinese into output |
| Code changes / refactoring | Depends on existing codebase context |
| Architecture design / proposals | Requires project knowledge |
| Debugging / error analysis | Requires accurate reasoning |
| Code review / audit | Quality gate must be GLM-level |
| Security decisions | Risk assessment needs precision |

## Workflow

1. **Identify** the task type from the routing table above
2. **Select** the most specific MiniMax MCP tool — prefer specialized tools over `minimax_ask`
3. **Execute** the task via the selected MCP tool
4. **Review** — if the output is code, architectural decisions, or affects existing codebase, have GLM review before applying
5. **Report** results to the user

## Anti-patterns

- Do not use MiniMax for tasks that require understanding existing project structure or dependencies
- Do not use MiniMax for translation — always route to GLM
- If MiniMax output needs correction, fix it via GLM rather than re-prompting MiniMax (costs more GLM to fix than to do it right the first time)
