---
name: medium-article
description: "Write high-quality Medium articles from scratch or by analyzing a git repository. Use this skill whenever the user mentions writing a Medium post, article, or blog post; turning a project or repo into an article; documenting open-source work; writing a technical post for publication; creating developer content; or publishing a writeup about code, a library, a tool, or a side project. Trigger even if they just say 'write an article about X' or 'help me write a post on Medium' — any article-writing intent qualifies. Also trigger when the user provides a GitHub/GitLab/Bitbucket URL and wants content derived from it."
---

# Medium Article Skill

Produce polished, publication-ready Medium articles — either from a topic prompt or by fully analyzing a git repository. Output is a `.md` file ready to paste or import into Medium.

---

## Workflow

### Step 1 — Understand the input

**Case A — Topic only** (no repo): go to Step 2 immediately.

**Case B — Git repository provided**:

```bash
# Clone (shallow — enough for analysis)
git clone --depth=1 <REPO_URL> /tmp/repo-analysis
```

Then run the repo analysis pipeline (see **Repository Analysis** section below) before writing.

**Case C — Local files uploaded**: read them via the file tools and treat as Case B.

---

### Step 2 — Gather article parameters

Before writing, collect (infer from context if obvious, otherwise ask):

| Parameter | Default |
|---|---|
| Target audience | Intermediate developers |
| Tone | Conversational but technical |
| Desired length | 1 500 – 2 500 words |
| Article angle | See §Angles below |
| Personal voice/author name | Anonymous / user-provided |
| Include code snippets? | Yes, if a repo was analyzed |

**Angles** (pick one or propose):
- *"I built X — here's how"* — first-person walkthrough of decisions
- *"Why X solves Y problem"* — problem/solution framing
- *"Deep dive into X"* — technical reference
- *"X vs Y"* — comparison
- *"Lessons learned"* — retrospective

---

### Step 3 — Repository Analysis (only for Case B/C)

Run the analysis script, then synthesize findings:

```bash
python3 /mnt/skills/user/medium-article/scripts/analyze_repo.py /tmp/repo-analysis
```

The script outputs a JSON summary. Read it and extract:

1. **Project identity** — name, description, license, primary language(s)
2. **Architecture** — directory tree, key modules, entry points
3. **Tech stack** — frameworks, major dependencies (from `requirements.txt`, `Cargo.toml`, `package.json`, `go.mod`, `pom.xml`, etc.)
4. **Core logic** — scan the most important source files (prioritize `src/`, `lib/`, `core/`, `main.*`) and understand what they do
5. **API surface** — public functions, classes, CLI commands, REST endpoints, MCP tools
6. **README signals** — motivation, install instructions, usage examples, roadmap
7. **Tests** — test files reveal intended behaviour; scan them
8. **Git history (if available)** — `git log --oneline -20` shows evolution and recent work
9. **Notable patterns** — design decisions, interesting algorithms, unusual choices worth highlighting in the article

Read up to **50 key files** if the repo is large. Prefer depth over breadth: understand 5 files well rather than skimming 50.

---

### Step 4 — Draft the article

Follow the **Medium Article Structure** (see `references/article-structure.md`).

Key rules:
- Open with a hook — a question, a bold claim, or a relatable pain point. Never start with "In this article…"
- Use the inverted pyramid: most important insight first
- Every H2 section must deliver standalone value
- Code blocks: use triple backtick fences with language tag; include only illustrative snippets (max ~30 lines each), not entire files
- Images: use `![alt](url)` placeholders labeled `[IMAGE: description]` so the author can fill them in
- Callout boxes: use `> **💡 Tip:** ...` blockquotes for tips and `> **⚠️ Note:** ...` for warnings
- End with a concrete CTA (GitHub star, newsletter, follow, comment question)
- Include a **TL;DR** section right after the title/intro if length > 1 500 words

---

### Step 5 — Generate metadata block

Prepend the article with a metadata header (stripped before publishing):

```
---
title: <title>
subtitle: <subtitle — one sentence, no period>
tags: [tag1, tag2, tag3, tag4, tag5]  # max 5, Medium limit
estimated_read_time: X min
audience: <beginner|intermediate|advanced>
angle: <chosen angle>
---
```

---

### Step 6 — Deliver as file

Always save the final article to `/mnt/user-data/outputs/<slug>.md` and present it with `present_files`. Never dump the full article inline in chat — it's too long.

After presenting, give the user a **3-line summary**:
1. What angle the article takes
2. Word count and estimated read time
3. One suggestion for improvement (image to add, section to expand, etc.)

---

## Repository Analysis Script

Read the script before running: `scripts/analyze_repo.py`

If the script is missing or fails, do the analysis manually:

```bash
# Project overview
cat /tmp/repo-analysis/README.md 2>/dev/null | head -100
find /tmp/repo-analysis -name "*.toml" -o -name "*.json" -o -name "*.yaml" | grep -E "(Cargo|package|pyproject|go\.mod)" | head -5

# Structure
find /tmp/repo-analysis -type f | grep -v ".git" | sort | head -80

# Dependency files
cat /tmp/repo-analysis/Cargo.toml 2>/dev/null
cat /tmp/repo-analysis/requirements.txt 2>/dev/null
cat /tmp/repo-analysis/package.json 2>/dev/null

# Key source files (read the most important ones in full)
# Prioritize: main entry point, core module, public API

# Git log
cd /tmp/repo-analysis && git log --oneline -20 2>/dev/null
```

---

## Quality Checklist (self-review before delivering)

- [ ] Hook in first paragraph — not "In this article…"
- [ ] TL;DR present (if >1500 words)
- [ ] No section longer than 400 words without a subheading or visual break
- [ ] At least one code snippet (if technical article)
- [ ] `[IMAGE: ...]` placeholders in natural spots
- [ ] CTA at the end
- [ ] Tags are specific (not just "programming" — use "rust", "open-source", "llm", etc.)
- [ ] Metadata block present
- [ ] File saved to `/mnt/user-data/outputs/`

---

## References

- `references/article-structure.md` — detailed section-by-section template
- `references/medium-formatting.md` — Medium-specific markdown quirks and import tips
- `scripts/analyze_repo.py` — automated repo analysis script
