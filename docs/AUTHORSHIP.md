# Authorship policy

AI coding agents (Cursor, Claude Code, Copilot, etc.) PRs are **drafts only**. Do not merge them.

1. Re-author the same tree as GitHub user `Unka-Malloc`.
2. Open a human-signed PR.
3. Close the Cursor PR without merging.

CI workflow `reject-ai-authors` fails if any commit on the PR is still AI/bot-authored, so a draft cannot be merged by mistake.
