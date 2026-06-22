---
name: architecture-update
description: Generates high-level architecture snapshots comparing the current branch with main and documents them in docs/architecture.
---
# Skill: Architecture Update
...
This skill automates the process of generating high-level architecture snapshots for the project.

## Workflow

1. **Identify Changes:**
   - Determine the base branch (usually `origin/main`).
   - Identify changed Python files compared to the base branch.
   - List commits between base and current head.

2. **Generate Snapshot:**
   - Create a new file in `docs/architecture/` with the current date: `YYYY-MM-DD-architecture.md`.
   - Populate with:
     - Purpose (Brief explanation of changes).
     - Overview (Purpose, key shifts, core components changed).
     - Dataflow (If applicable).
     - Key design decisions.
     - Next steps/improvements.
     - Commits list.
     - Changed files list.

3. **Update Registry:**
   - Update `docs/architecture/README.md` to include the new entry in the table.

## Usage
Run this skill when major architectural changes are committed to the codebase to maintain up-to-date documentation.
