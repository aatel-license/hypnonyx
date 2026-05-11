# Medium Formatting Reference

## What Medium Supports (as of 2025)

### ✅ Works natively
- `# H1` — becomes the article title (only use once, at the top)
- `## H2` — main section headers
- `### H3` — subsection headers (avoid H4+ — not well rendered)
- `**bold**` and `*italic*`
- `` `inline code` ``
- ` ```lang ... ``` ` — fenced code blocks (language hint respected for syntax color)
- `> blockquote` — renders as styled pull quote
- `- ` and `1. ` — unordered and ordered lists
- `![alt](url)` — inline images (must be publicly accessible URLs)
- `[text](url)` — hyperlinks
- `---` — horizontal rule / section divider

### ⚠️ Partial / quirky
- Tables: Medium does **not** support markdown tables natively. Convert to plain prose or use an image.
- Nested lists: renders, but avoid going deeper than 2 levels.
- Footnotes: not supported. Convert to inline parenthetical or a "Notes" section.
- HTML tags: stripped. Never include raw HTML.
- LaTeX/math: not supported. Write math in plain text or use an image.

### ❌ Not supported
- `----` YAML frontmatter — strip before importing
- Emoji in headings can break rendering on some clients — use sparingly
- `<details>` / `<summary>` — stripped
- Syntax highlighting labels that are too exotic (stick to: `python`, `javascript`, `typescript`, `rust`, `go`, `bash`, `json`, `yaml`, `sql`, `cpp`, `java`, `kotlin`)

---

## Code Block Best Practices

```rust
// Good: short, illustrative, with a comment explaining intent
fn choose(&self, memories: &[Memory]) -> Option<&Memory> {
    // Apply recency bias and emotional weight before sampling
    let scored = self.score_all(memories);
    self.weighted_sample(&scored)
}
```

- Max 30 lines per block
- Always include a language identifier
- Add a comment on the most non-obvious line
- If the snippet needs context, add 2–3 lines of setup even if slightly redundant

---

## Image Placeholders (use in drafts)

```markdown
[IMAGE: Hero — screenshot of the tool's main interface]
[IMAGE: Architecture diagram — boxes showing DB → Brain → FastAPI → MCP]
[IMAGE: Terminal output — running the CLI demo]
[IMAGE: Benchmark — bar chart comparing latency before/after]
```

Replace with real URLs before publishing. Recommended free sources:
- Your own screenshots (best)
- Excalidraw diagrams (excalidraw.com) → export PNG → upload to Medium
- Carbon (carbon.now.sh) for beautiful code screenshots

---

## Canonical URL

If cross-posting from a personal blog or dev.to:

After import, in the Medium editor:
`Story settings → Advanced settings → Originally published at → [your URL]`

This prevents SEO duplication penalties.

---

## Tags Strategy

Medium shows articles to followers of tags. Use all 5 slots:

| Slot | Strategy |
|---|---|
| 1 | Most specific (e.g., `rust`, `python`, `llm`) |
| 2 | Technology umbrella (e.g., `programming`, `software-development`) |
| 3 | Topic (e.g., `open-source`, `machine-learning`, `databases`) |
| 4 | Audience (e.g., `software-engineering`, `devops`) |
| 5 | Format or trend (e.g., `tutorial`, `ai`, `web-development`) |

---

## Read Time Estimation

Medium shows "X min read" automatically (250 words/min).
- 1 500 words → ~6 min
- 2 000 words → ~8 min
- 2 500 words → ~10 min

Aim for 5–8 minutes for best engagement. Under 3 min feels thin; over 12 min loses casual readers.
