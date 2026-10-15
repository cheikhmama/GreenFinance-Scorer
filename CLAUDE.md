# CLAUDE.md

Instructions for Claude Code working in this repository.

## `/summary` — last execution summary

Whenever the user types `/summary` or asks for a summary of the last turn, respond with exactly
this structure (and nothing else around it):

---
### 📊 Last Execution Summary

- **📁 Files Changed:** (List modified, added, or deleted files with brief notes)
- **🗄️ Database & Schema Changes:** (List modified SQLAlchemy models, Alembic migrations, or database cleanup done)
- **⚙️ Core Logic & Features:** (Briefly explain what features, services, or fixes were implemented)
- **✅ Tasks Completed:** (Check off corresponding items from `docs/TASKS.md`)
- **▶️ Next Step:** (State the immediate next task to be executed)
---

Rules for filling it in:
- Base every line on what actually happened (git status/diff/log, tool results); never on intent.
- Write "None" for a section with nothing to report instead of dropping it.
- Tasks Completed lists only items that are really ticked in `docs/TASKS.md`.
