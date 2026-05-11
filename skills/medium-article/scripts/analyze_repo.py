#!/usr/bin/env python3
"""
analyze_repo.py — Automated git repository analysis for Medium article generation.

Usage:
    python3 analyze_repo.py <repo_path> [--output json|text] [--max-files N]

Output (JSON):
    {
      "name": str,
      "description": str,
      "language_breakdown": {lang: file_count},
      "primary_language": str,
      "tech_stack": [str],
      "structure": {directory_tree},
      "entry_points": [str],
      "key_files": [{path, size_lines, summary_hint}],
      "dependencies": {manager: [dep]},
      "readme_excerpt": str,
      "git_log": [str],
      "has_tests": bool,
      "test_files": [str],
      "api_surface_hints": [str],
      "license": str,
      "stats": {total_files, total_lines, languages}
    }
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "out", ".cache", ".next", ".nuxt",
    "vendor", "third_party", ".idea", ".vscode", "coverage",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".tar", ".gz",
    ".lock",  # lockfiles are noisy
}

LANGUAGE_MAP = {
    ".py": "Python", ".rs": "Rust", ".go": "Go", ".ts": "TypeScript",
    ".tsx": "TypeScript/React", ".js": "JavaScript", ".jsx": "JavaScript/React",
    ".java": "Java", ".kt": "Kotlin", ".cpp": "C++", ".c": "C",
    ".h": "C/C++ Header", ".cs": "C#", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".dart": "Dart", ".lua": "Lua", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "SASS",
    ".sql": "SQL", ".r": "R", ".jl": "Julia", ".ex": "Elixir",
    ".exs": "Elixir", ".hs": "Haskell", ".clj": "Clojure",
    ".toml": "TOML Config", ".yaml": "YAML Config", ".yml": "YAML Config",
    ".json": "JSON Config", ".md": "Markdown", ".mdx": "MDX",
}

DEPENDENCY_FILES = {
    "requirements.txt": "pip",
    "pyproject.toml": "pip/poetry",
    "setup.py": "pip",
    "Pipfile": "pipenv",
    "Cargo.toml": "cargo",
    "package.json": "npm/yarn",
    "go.mod": "go modules",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "Gemfile": "bundler",
    "composer.json": "composer",
    "mix.exs": "mix",
    "cabal.project": "cabal",
    "flake.nix": "nix",
}

ENTRY_POINT_PATTERNS = [
    "main.py", "main.rs", "main.go", "main.js", "main.ts",
    "index.py", "index.js", "index.ts", "app.py", "app.js", "app.ts",
    "server.py", "server.js", "server.ts", "cli.py", "cli.rs",
    "__main__.py", "src/main.rs", "src/main.py", "src/lib.rs",
    "src/index.ts", "src/index.js",
]

TEST_PATTERNS = ["test_", "_test.", ".test.", ".spec.", "tests/", "test/", "__tests__/"]

API_HINTS = [
    "FastAPI", "Flask", "Django", "Express", "Axum", "Actix", "Gin",
    "@app.route", "@router", "Router::new", "HttpServer", "MCP",
    "tool_calls", "openai", "anthropic", "langchain",
]

MAX_FILE_CONTENT_LINES = 200  # lines to read per key file for hints
MAX_KEY_FILES = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, cwd=None, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=cwd, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def count_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def read_head(path, n=100):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readline() for _ in range(n))
    except Exception:
        return ""


def short_summary_hint(path, content):
    """Extract a one-line hint about what a file does."""
    lines = content.splitlines()
    # Docstring / module comment
    for line in lines[:20]:
        s = line.strip().lstrip("#").lstrip("//").lstrip("/*").lstrip("*").strip()
        if len(s) > 20 and not s.startswith("!"):
            return s[:120]
    return ""


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def collect_files(repo_path):
    """Walk the repo and return a list of (relative_path, absolute_path) for source files."""
    files = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in SKIP_EXTENSIONS:
                continue
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, repo_path)
            files.append((rel_path, abs_path))
    return files


def build_language_breakdown(files):
    counter = Counter()
    for rel, _ in files:
        ext = Path(rel).suffix.lower()
        lang = LANGUAGE_MAP.get(ext)
        if lang and "Config" not in lang and "Markdown" not in lang:
            counter[lang] += 1
    return dict(counter.most_common(10))


def find_entry_points(files):
    rel_paths = {rel for rel, _ in files}
    found = []
    for pattern in ENTRY_POINT_PATTERNS:
        for rel in rel_paths:
            if rel == pattern or rel.endswith("/" + pattern):
                found.append(rel)
    return list(set(found))[:5]


def find_test_files(files):
    test_files = []
    for rel, _ in files:
        if any(p in rel for p in TEST_PATTERNS):
            test_files.append(rel)
    return test_files[:10]


def parse_dependencies(repo_path):
    deps = {}
    for fname, manager in DEPENDENCY_FILES.items():
        fpath = os.path.join(repo_path, fname)
        if os.path.exists(fpath):
            content = read_head(fpath, 60)
            deps[manager] = _extract_dep_names(fname, content)
    return deps


def _extract_dep_names(fname, content):
    names = []
    if fname == "requirements.txt":
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line.split("==")[0].split(">=")[0].split("[")[0].strip())
    elif fname == "Cargo.toml":
        in_deps = False
        for line in content.splitlines():
            if "[dependencies]" in line or "[dev-dependencies]" in line:
                in_deps = True
                continue
            if in_deps and line.startswith("["):
                in_deps = False
            if in_deps and "=" in line:
                names.append(line.split("=")[0].strip().strip('"'))
    elif fname == "package.json":
        import re
        for m in re.finditer(r'"([^"@][^"]+)"\s*:', content):
            n = m.group(1)
            if n not in ("name", "version", "description", "scripts", "main", "license"):
                names.append(n)
    return names[:20]


def find_api_surface_hints(files, repo_path):
    hints = set()
    for rel, abs_path in files[:50]:
        content = read_head(abs_path, 60)
        for hint in API_HINTS:
            if hint in content:
                hints.add(hint)
    return sorted(hints)


def select_key_files(files, entry_points):
    """Rank files by importance for article writing."""
    scored = []
    priority_dirs = {"src", "lib", "core", "pkg", "internal", "api", "server"}
    priority_names = {"main", "lib", "core", "api", "server", "router", "handler",
                      "engine", "brain", "memory", "db", "model", "client"}

    for rel, abs_path in files:
        ext = Path(rel).suffix.lower()
        if ext in SKIP_EXTENSIONS or ext in {".md", ".toml", ".json", ".yaml", ".yml", ".txt"}:
            continue
        score = 0
        parts = Path(rel).parts
        name = Path(rel).stem.lower()

        if rel in entry_points:
            score += 10
        if any(d in priority_dirs for d in parts):
            score += 3
        if any(n in name for n in priority_names):
            score += 2
        if "test" in rel.lower():
            score -= 1
        lines = count_lines(abs_path)
        if 50 < lines < 500:
            score += 2  # sweet spot — readable but substantial
        scored.append((score, lines, rel, abs_path))

    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [(rel, abs_path) for _, _, rel, abs_path in scored[:MAX_KEY_FILES]]


def build_directory_tree(repo_path, max_depth=3):
    tree = {}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        depth = os.path.relpath(root, repo_path).count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue
        rel_root = os.path.relpath(root, repo_path)
        tree[rel_root] = [f for f in files if Path(f).suffix not in SKIP_EXTENSIONS]
    return tree


def get_readme(repo_path):
    for fname in ["README.md", "README.rst", "README.txt", "README"]:
        fpath = os.path.join(repo_path, fname)
        if os.path.exists(fpath):
            return read_head(fpath, 80)
    return ""


def get_git_info(repo_path):
    log = run("git log --oneline -20", cwd=repo_path)
    name = run("git remote get-url origin 2>/dev/null || echo ''", cwd=repo_path)
    return {
        "log": log.splitlines() if log else [],
        "remote": name,
    }


def get_license(repo_path):
    for fname in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]:
        fpath = os.path.join(repo_path, fname)
        if os.path.exists(fpath):
            first_line = read_head(fpath, 3)
            return first_line.strip()[:100]
    return "Unknown"


def get_project_name_description(repo_path, readme):
    name = Path(repo_path).name
    desc = ""
    # Try to extract from README first line with content
    for line in readme.splitlines():
        line = line.strip().lstrip("#").strip()
        if len(line) > 10:
            desc = line[:200]
            break
    # Try package.json or Cargo.toml
    for fpath in [os.path.join(repo_path, "Cargo.toml"),
                  os.path.join(repo_path, "package.json"),
                  os.path.join(repo_path, "pyproject.toml")]:
        if os.path.exists(fpath):
            content = read_head(fpath, 20)
            for line in content.splitlines():
                if "name" in line and "=" in line:
                    n = line.split("=")[-1].strip().strip('"').strip("'")
                    if n:
                        name = n
                        break
                if "description" in line and "=" in line and not desc:
                    d = line.split("=", 1)[-1].strip().strip('"').strip("'")
                    if len(d) > 10:
                        desc = d[:200]
    return name, desc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze(repo_path, max_files=MAX_KEY_FILES):
    repo_path = str(Path(repo_path).resolve())
    if not os.path.isdir(repo_path):
        print(json.dumps({"error": f"Path not found: {repo_path}"}))
        sys.exit(1)

    files = collect_files(repo_path)
    lang_breakdown = build_language_breakdown(files)
    primary_lang = next(iter(lang_breakdown), "Unknown")
    entry_points = find_entry_points(files)
    test_files = find_test_files(files)
    deps = parse_dependencies(repo_path)
    api_hints = find_api_surface_hints(files, repo_path)
    key_files_raw = select_key_files(files, entry_points)
    readme = get_readme(repo_path)
    git_info = get_git_info(repo_path)
    license_text = get_license(repo_path)
    name, description = get_project_name_description(repo_path, readme)
    tree = build_directory_tree(repo_path)

    # Build key_files summary
    key_files = []
    for rel, abs_path in key_files_raw:
        content = read_head(abs_path, MAX_FILE_CONTENT_LINES)
        key_files.append({
            "path": rel,
            "size_lines": count_lines(abs_path),
            "summary_hint": short_summary_hint(rel, content),
            "content_preview": content[:1500],  # first 1500 chars for Claude to read
        })

    # Tech stack = all dep managers + frameworks detected
    tech_stack = []
    for mgr, dep_list in deps.items():
        tech_stack.append(mgr)
        tech_stack.extend(dep_list[:5])
    tech_stack.extend(api_hints)
    tech_stack = list(dict.fromkeys(tech_stack))[:25]  # deduplicate, cap at 25

    # Stats
    total_lines = sum(count_lines(abs_path) for _, abs_path in files
                      if Path(abs_path).suffix not in SKIP_EXTENSIONS)

    result = {
        "name": name,
        "description": description,
        "primary_language": primary_lang,
        "language_breakdown": lang_breakdown,
        "tech_stack": tech_stack,
        "structure": {k: v for k, v in list(tree.items())[:30]},
        "entry_points": entry_points,
        "key_files": key_files,
        "dependencies": deps,
        "readme_excerpt": readme[:3000],
        "git_log": git_info["log"],
        "git_remote": git_info["remote"],
        "has_tests": bool(test_files),
        "test_files": test_files,
        "api_surface_hints": api_hints,
        "license": license_text,
        "stats": {
            "total_source_files": len(files),
            "total_lines": total_lines,
            "languages": list(lang_breakdown.keys()),
        },
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze a git repo for Medium article generation")
    parser.add_argument("repo_path", help="Path to the cloned repository")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--max-files", type=int, default=MAX_KEY_FILES)
    args = parser.parse_args()

    result = analyze(args.repo_path, max_files=args.max_files)

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Project: {result['name']}")
        print(f"Description: {result['description']}")
        print(f"Primary language: {result['primary_language']}")
        print(f"Tech stack: {', '.join(result['tech_stack'][:10])}")
        print(f"Entry points: {', '.join(result['entry_points'])}")
        print(f"Tests: {'Yes' if result['has_tests'] else 'No'}")
        print(f"Files: {result['stats']['total_source_files']} | Lines: {result['stats']['total_lines']:,}")
        print(f"\nKey files to read:")
        for kf in result["key_files"]:
            print(f"  {kf['path']} ({kf['size_lines']} lines) — {kf['summary_hint'][:60]}")


if __name__ == "__main__":
    main()
