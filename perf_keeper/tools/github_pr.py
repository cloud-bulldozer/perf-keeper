"""GitHub pull request metadata via the REST API (not HTML PR pages)."""
from __future__ import annotations

import os
import re

import httpx
from langchain_core.tools import tool

_GITHUB_PULL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)(?:/|$|\?)",
    re.IGNORECASE,
)


def _parse_pr_url(pr_url: str) -> tuple[str, str, str] | None:
    pr_url = pr_url.strip()
    m = _GITHUB_PULL_RE.match(pr_url)
    if not m:
        return None
    return m.group("owner"), m.group("repo"), m.group("number")


def _format_pr_response(data: dict) -> str:
    body = (data.get("body") or "").strip()
    max_body = 12_000
    if len(body) > max_body:
        body = body[:max_body] + "\n\n...[body truncated]"
    labels = [lb.get("name", "") for lb in (data.get("labels") or []) if isinstance(lb, dict)]
    lines = [
        f"title: {data.get('title')}",
        f"state: {data.get('state')} merged: {data.get('merged')}",
        f"author: {(data.get('user') or {}).get('login')}",
        f"html_url: {data.get('html_url')}",
        f"labels: {', '.join(labels) if labels else '(none)'}",
        "",
        "body:",
        body or "(empty)",
    ]
    return "\n".join(lines)


@tool
def fetch_github_pull_request(pr_url: str) -> str:
    """Fetch a GitHub pull request title, body, labels, and state via the REST API.

    Use this for ``https://github.com/<owner>/<repo>/pull/<number>`` URLs (for example
    from Orion "Related PRs"). Do **not** use ``fetch_artifact`` for GitHub PR pages;
    those return HTML. Pass the same browser URL here.

    Args:
        pr_url: Full GitHub pull request URL, optionally with trailing path segments.
    """
    parsed = _parse_pr_url(pr_url)
    if not parsed:
        return (
            "Invalid or unsupported GitHub PR URL. Expected "
            "https://github.com/<owner>/<repo>/pull/<number>"
        )
    owner, repo, number = parsed
    api_base = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    url = f"{api_base}/repos/{owner}/{repo}/pulls/{number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=60.0)
        resp.raise_for_status()
        return _format_pr_response(resp.json())
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 404:
            return "GitHub API: pull request not found (404)."
        if e.response is not None and e.response.status_code in (401, 403):
            return (
                "GitHub API: access denied. Set GITHUB_TOKEN in the environment "
                f"for private repos or rate limits. ({e.response.status_code})"
            )
        return f"GitHub API error: {e}"
    except Exception as e:
        return f"Error fetching GitHub pull request: {e}"
