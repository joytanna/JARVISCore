"""
GitHub Integration — repos, issues, PRs, file reading, code search.
Uses GitHub REST API v3 with optional PAT token for higher rate limits.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen, Request

import config
from tools.registry import register

_TOKEN_FILE = config.MEMORY_DIR / ".github_token"


def _gh_token() -> str:
    # Check env first, then file
    t = os.environ.get("GITHUB_TOKEN","")
    if not t and _TOKEN_FILE.exists():
        t = _TOKEN_FILE.read_text().strip()
    return t


def _gh_get(endpoint: str) -> dict | list:
    token = _gh_token()
    url   = f"https://api.github.com{endpoint}"
    headers = {
        "User-Agent":  "JARVIS/1.0",
        "Accept":      "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req  = Request(url, headers=headers)
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _gh_post(endpoint: str, body: dict) -> dict:
    import urllib.request
    token = _gh_token()
    url   = f"https://api.github.com{endpoint}"
    headers = {
        "User-Agent":  "JARVIS/1.0",
        "Accept":      "application/vnd.github+json",
        "Content-Type":"application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode()
    req  = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read())


@register(
    name="set_github_token",
    description="Save a GitHub Personal Access Token for authenticated API access.",
    parameters={"type":"object","properties":{
        "token":{"type":"string","description":"GitHub PAT (ghp_...)"},
    },"required":["token"]},
)
def set_github_token(token: str) -> str:
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token.strip())
    return "GitHub token saved, sir. Higher rate limits and private repos now accessible."


@register(
    name="list_repos",
    description="List GitHub repositories for a user or organisation.",
    parameters={"type":"object","properties":{
        "username":{"type":"string","description":"GitHub username or org"},
        "max":     {"type":"integer","description":"Max repos to return (default 10)"},
    },"required":["username"]},
)
def list_repos(username: str, max: int = 10) -> str:
    try:
        data = _gh_get(f"/users/{username}/repos?sort=updated&per_page={max}")
        if not data:
            return f"No public repos found for '{username}', sir."
        lines = []
        for r in data[:max]:
            lang    = r.get("language") or "—"
            stars   = r.get("stargazers_count", 0)
            updated = r.get("updated_at","")[:10]
            desc    = (r.get("description") or "")[:60]
            lines.append(f"⭐{stars:>5} [{lang:12}] {r['name']:30} {updated}\n         {desc}")
        return f"Repos for {username}:\n" + "\n".join(lines)
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="get_repo_info",
    description="Get detailed info about a GitHub repository.",
    parameters={"type":"object","properties":{
        "repo":{"type":"string","description":"owner/repo, e.g. 'microsoft/vscode'"},
    },"required":["repo"]},
)
def get_repo_info(repo: str) -> str:
    try:
        r = _gh_get(f"/repos/{repo}")
        lines = [
            f"📁 {r['full_name']}",
            f"⭐ Stars: {r.get('stargazers_count',0):,}",
            f"🍴 Forks: {r.get('forks_count',0):,}",
            f"👁  Watchers: {r.get('watchers_count',0):,}",
            f"🔤 Language: {r.get('language','—')}",
            f"📜 License: {(r.get('license') or {}).get('name','—')}",
            f"📅 Created: {r.get('created_at','')[:10]}",
            f"🔄 Updated: {r.get('updated_at','')[:10]}",
            f"🔗 URL: {r.get('html_url','')}",
            f"\n{r.get('description','')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="get_issues",
    description="List open issues in a GitHub repository.",
    parameters={"type":"object","properties":{
        "repo":  {"type":"string","description":"owner/repo"},
        "state": {"type":"string","description":"open / closed / all (default open)"},
        "max":   {"type":"integer","description":"Max issues (default 10)"},
    },"required":["repo"]},
)
def get_issues(repo: str, state: str = "open", max: int = 10) -> str:
    try:
        issues = _gh_get(f"/repos/{repo}/issues?state={state}&per_page={max}")
        prs    = [i for i in issues if "pull_request" in i]
        issues = [i for i in issues if "pull_request" not in i]
        if not issues:
            return f"No {state} issues in {repo}, sir."
        lines = []
        for i in issues[:max]:
            labels = ", ".join(l["name"] for l in i.get("labels",[]))
            label_str = f"  [{labels}]" if labels else ""
            lines.append(f"#{i['number']:>5} {i['title'][:60]}{label_str}")
        return f"Issues in {repo} ({state}):\n" + "\n".join(lines)
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="get_pull_requests",
    description="List pull requests in a GitHub repository.",
    parameters={"type":"object","properties":{
        "repo":  {"type":"string","description":"owner/repo"},
        "state": {"type":"string","description":"open / closed / all (default open)"},
        "max":   {"type":"integer","description":"Max PRs (default 10)"},
    },"required":["repo"]},
)
def get_pull_requests(repo: str, state: str = "open", max: int = 10) -> str:
    try:
        prs = _gh_get(f"/repos/{repo}/pulls?state={state}&per_page={max}")
        if not prs:
            return f"No {state} pull requests in {repo}, sir."
        lines = []
        for p in prs[:max]:
            author = p.get("user",{}).get("login","?")
            lines.append(f"#{p['number']:>5} [{author:15}] {p['title'][:55]}")
        return f"Pull Requests in {repo} ({state}):\n" + "\n".join(lines)
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="read_file_github",
    description="Read a file from a GitHub repository.",
    parameters={"type":"object","properties":{
        "repo":  {"type":"string","description":"owner/repo"},
        "path":  {"type":"string","description":"File path in repo"},
        "branch":{"type":"string","description":"Branch (default main)"},
    },"required":["repo","path"]},
)
def read_file_github(repo: str, path: str, branch: str = "main") -> str:
    try:
        import base64
        data = _gh_get(f"/repos/{repo}/contents/{path}?ref={branch}")
        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            if len(content) > 4000:
                content = content[:4000] + f"\n…[{len(content)} total chars]"
            return f"📄 {repo}/{path} ({branch}):\n\n{content}"
        return f"File at {path} is not text-decodable, sir."
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="search_github",
    description="Search GitHub repositories, code, or issues.",
    parameters={"type":"object","properties":{
        "query":{"type":"string","description":"Search query"},
        "type": {"type":"string","description":"repositories / code / issues (default repositories)"},
        "max":  {"type":"integer","description":"Max results (default 5)"},
    },"required":["query"]},
)
def search_github(query: str, type: str = "repositories", max: int = 5) -> str:
    try:
        q    = quote_plus(query)
        data = _gh_get(f"/search/{type}?q={q}&per_page={max}")
        items= data.get("items", [])
        if not items:
            return f"No GitHub {type} found for '{query}', sir."
        lines = []
        for item in items[:max]:
            if type == "repositories":
                lines.append(f"⭐{item.get('stargazers_count',0):>5} {item['full_name']}  —  {item.get('description','')[:60]}")
            elif type == "code":
                lines.append(f"• {item['repository']['full_name']}/{item['path']}")
            elif type == "issues":
                lines.append(f"#{item['number']} {item['title']}  [{item['state']}]")
        return f"GitHub {type} results for '{query}':\n" + "\n".join(lines)
    except Exception as e:
        return f"GitHub search error: {e}"


@register(
    name="create_github_issue",
    description="Create a new issue in a GitHub repository.",
    parameters={"type":"object","properties":{
        "repo":  {"type":"string","description":"owner/repo"},
        "title": {"type":"string"},
        "body":  {"type":"string","description":"Issue description"},
        "labels":{"type":"string","description":"Comma-separated labels (optional)"},
    },"required":["repo","title"]},
)
def create_github_issue(repo: str, title: str, body: str = "", labels: str = "") -> str:
    if not _gh_token():
        return "GitHub token required to create issues. Set one with set_github_token, sir."
    try:
        payload: dict = {"title": title, "body": body}
        if labels:
            payload["labels"] = [l.strip() for l in labels.split(",")]
        result = _gh_post(f"/repos/{repo}/issues", payload)
        return f"Issue #{result['number']} created: {result['html_url']}, sir."
    except Exception as e:
        return f"GitHub error: {e}"


@register(
    name="get_trending_repos",
    description="Get trending GitHub repositories today.",
    parameters={"type":"object","properties":{
        "language":{"type":"string","description":"Filter by language (optional)"},
        "max":     {"type":"integer","description":"Max results (default 8)"},
    }},
)
def get_trending_repos(language: str = "", max: int = 8) -> str:
    try:
        # Use GitHub search as proxy for trending (sorted by stars, recent)
        q   = f"stars:>100 created:>2024-01-01"
        if language:
            q += f" language:{language}"
        data = _gh_get(f"/search/repositories?q={quote_plus(q)}&sort=stars&order=desc&per_page={max}")
        items = data.get("items",[])
        if not items:
            return "No trending repos found, sir."
        lines = []
        for r in items[:max]:
            lines.append(f"⭐{r.get('stargazers_count',0):>7,} {r['full_name']:35} {r.get('description','')[:50]}")
        return f"Trending GitHub repos{' ('+language+')' if language else ''}:\n" + "\n".join(lines)
    except Exception as e:
        return f"GitHub error: {e}"
