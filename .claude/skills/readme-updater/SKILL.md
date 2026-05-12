---
name: readme-updater
description: >
  Automatically update a project's root README.md to reflect the latest changes in
  the codebase. Use this skill whenever the user wants to sync their README with recent
  work — phrases like "update my README", "my README is outdated", "reflect latest
  changes in README", "add new features to README", "README doesn't mention X", or
  "generate/rewrite README from my code". Also trigger when the user shares a
  git diff, changelog, or new file list and wants the README updated. Works for any
  project type: Node.js, Python, Next.js, FastAPI, React, monorepos, etc.
---

# README Updater Skill

Updates a project's root `README.md` to stay in sync with actual code changes,
without rewriting sections that are still accurate.

---

## Workflow

### Step 1 — Gather context

Collect information in this order (stop early if you have enough):

1. **README path** — check for `README.md` at project root; ask if absent.
2. **Read the current README** — understand what it already covers.
3. **Detect recent changes** — in priority order:
   - If the user provides a git diff or changelog, use it directly.
   - If you have bash access: run `git log --oneline -20` and `git diff HEAD~5 --stat` from the project root to identify changed files and commit messages.
   - If neither: ask the user to describe what changed (new features, removed things, renamed commands, updated dependencies, etc.).
4. **Inspect changed files** — for each significantly changed file, view it to understand the new behaviour. Focus on:
   - Entry points (`main.py`, `index.ts`, `app.py`, `server.js`, etc.)
   - Config files (`package.json`, `pyproject.toml`, `Cargo.toml`, `docker-compose.yml`)
   - New directories (new feature modules, routes, components)
   - `.env.example` or environment variable documentation

### Step 2 — Identify what needs updating

Produce a short internal checklist of **sections to change**, e.g.:

- [ ] Features list — add X, remove Y
- [ ] Installation — new dependency / changed command
- [ ] Environment variables — new vars added
- [ ] Usage examples — updated CLI flags or API endpoints
- [ ] Architecture overview — new module added
- [ ] Badges — version bump

Do **not** rewrite sections that are still accurate. Preserve the author's voice and structure.

### Step 3 — Draft the updated README

Apply only the necessary changes:

- **Add** new features, routes, commands, env vars that are now in the code but missing from the README.
- **Remove or update** stale information (old commands, deprecated config, removed features).
- **Update** version numbers, dependency names, or setup steps if they changed.
- **Preserve** style, tone, formatting conventions, existing sections that are still correct.

If the project has no README yet, generate a full one using the structure below.

### Step 4 — Output

- If you have bash/file access: write the updated README directly to the file path and confirm the change.
- Otherwise: output the full updated README as a markdown artifact the user can copy.

Always show a brief summary of what changed (bullet list of edits made).

---

## README structure for new projects

Use this when generating from scratch. Omit sections that don't apply.

```markdown
# Project Name

> One-line tagline

## Overview
2–4 sentences: what it does, who it's for, key tech.

## Features
- Bullet list of main capabilities

## Tech Stack
| Layer | Technology |
|-------|-----------|
| ...   | ...       |

## Prerequisites
- Node 20+ / Python 3.11+ / etc.
- Other system deps

## Installation
```bash
git clone ...
cd project
npm install   # or pip install -r requirements.txt
```

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| ...      | Yes      | ...         |

Copy `.env.example` to `.env` and fill in the values.

## Usage
```bash
npm run dev   # or python main.py
```

## API Reference (if applicable)
Brief table or list of key endpoints.

## Project Structure (if non-obvious)
```
src/
  features/
  ...
```

## Contributing
Short contributing guide or link.

## License
MIT / Apache-2.0 / etc.
```

---

## Edge cases

| Situation | Action |
|-----------|--------|
| No git history available | Ask user to describe changes; inspect `package.json` / `pyproject.toml` for version/dep clues |
| Monorepo | Update root README and note sub-packages; don't rewrite sub-package READMEs unless asked |
| README is in a non-standard location | Ask user to confirm path |
| README is very long (>500 lines) | Update only the specific sections that changed; don't regenerate entire file |
| No README exists | Generate from scratch using project structure + entry points |
| User specifies a changelog or PR description | Treat it as authoritative source of truth for what changed |

---

## Quality checklist before finishing

- [ ] All new CLI commands / API endpoints are documented
- [ ] All new required environment variables are listed
- [ ] Installation steps still work with the current dependency list
- [ ] No stale references to removed files, commands, or features
- [ ] Code examples use the correct syntax for the current version
- [ ] Badges (if present) reflect current versions