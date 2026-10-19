"""CP3 findings gate: fail CI on open SonarCloud findings the default Quality Gate lets through.

The default "Sonar way" gate only judges new code. On top of it this fails the build when the analysed
branch or pull request has any open vulnerability, any security hotspot still to review, or any
CRITICAL/BLOCKER code smell.

Environment: SONAR_TOKEN, SONAR_PROJECT_KEY, and one of SONAR_PULL_REQUEST or SONAR_BRANCH.
SONAR_HOST_URL defaults to https://sonarcloud.io. Standard library only.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

PAGE_SIZE = 100
MAX_LISTED = 20

CHECKS = (
    ("Vulnerabilities", "api/issues/search", {"types": "VULNERABILITY", "resolved": "false"}),
    ("Security hotspots to review", "api/hotspots/search", {"status": "TO_REVIEW"}),
    (
        "Critical/Blocker code smells",
        "api/issues/search",
        {"types": "CODE_SMELL", "severities": "CRITICAL,BLOCKER", "resolved": "false"},
    ),
)


def _get(host: str, token: str, path: str, params: dict[str, str]) -> dict:
    url = f"{host.rstrip('/')}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def _scope(project_key: str, path: str) -> dict[str, str]:
    key_param = "projectKey" if "hotspots" in path else "componentKeys"
    scope = {key_param: project_key, "ps": str(PAGE_SIZE)}
    if pull_request := os.environ.get("SONAR_PULL_REQUEST"):
        scope["pullRequest"] = pull_request
    elif branch := os.environ.get("SONAR_BRANCH"):
        scope["branch"] = branch
    return scope


def _describe(item: dict) -> str:
    location = item.get("component", "").split(":", 1)[-1]
    if line := item.get("line"):
        location = f"{location}:{line}"
    rule = item.get("rule") or item.get("ruleKey") or item.get("securityCategory", "")
    return f"{location} [{rule}] {item.get('message', '')}"


def main() -> int:
    host = os.environ.get("SONAR_HOST_URL") or "https://sonarcloud.io"
    token = os.environ.get("SONAR_TOKEN")
    project_key = os.environ.get("SONAR_PROJECT_KEY")
    if not token or not project_key:
        print("::error::SONAR_TOKEN and SONAR_PROJECT_KEY are required")
        return 2

    failed = False
    for title, path, filters in CHECKS:
        data = _get(host, token, path, {**_scope(project_key, path), **filters})
        items = data.get("issues", data.get("hotspots", []))
        total = data.get("paging", {}).get("total", data.get("total", len(items)))
        print(f"{title}: {total}")
        for item in items[:MAX_LISTED]:
            print(f"  - {_describe(item)}")
        if total:
            failed = True
            print(f"::error::{project_key}: {total} {title.lower()}")

    dashboard = f"{host.rstrip('/')}/dashboard?id={urllib.parse.quote(project_key)}"
    print(f"SonarCloud: {dashboard}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
