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
import time
import urllib.parse
import urllib.request

PAGE_SIZE = 100
MAX_LISTED = 20
# The issue search index can lag the Quality Gate result; wait until it matches the analysis measures.
INDEX_WAIT_SECONDS = int(os.environ.get("SONAR_INDEX_WAIT_SECONDS", "120"))
POLL_SECONDS = 5

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


def _measure_value(measure: dict) -> int:
    raw = measure.get("value")
    if raw is None:
        raw = measure.get("period", {}).get("value")
    if raw is None:
        raw = next((p.get("value") for p in measure.get("periods", []) if p.get("value") is not None), "0")
    return int(float(raw))


def _measures(host: str, token: str, project_key: str) -> dict[str, int]:
    keys = {
        "violations": "issues",
        "new_violations": "issues",
        "security_hotspots": "hotspots",
        "new_security_hotspots": "hotspots",
    }
    scope = _scope(project_key, "api/measures/component")
    scope.pop("componentKeys")
    scope.pop("ps")
    params = {**scope, "component": project_key, "metricKeys": ",".join(keys)}
    data = _get(host, token, "api/measures/component", params)
    found: dict[str, int] = {}
    for measure in data.get("component", {}).get("measures", []):
        name = keys.get(measure.get("metric"))
        if name:
            found[name] = max(found.get(name, 0), _measure_value(measure))
    return found


def _total(host: str, token: str, path: str, params: dict[str, str]) -> int:
    data = _get(host, token, path, {**params, "ps": "1"})
    return data.get("paging", {}).get("total", data.get("total", 0))


def _wait_for_index(host: str, token: str, project_key: str) -> None:
    expected = _measures(host, token, project_key)
    print(f"Analysis measures: {expected or 'none reported'}")
    probes = {
        "issues": ("api/issues/search", {"resolved": "false"}),
        "hotspots": ("api/hotspots/search", {"status": "TO_REVIEW"}),
    }
    deadline = time.monotonic() + INDEX_WAIT_SECONDS
    for name, (path, filters) in probes.items():
        want = expected.get(name, 0)
        previous = None
        while True:
            seen = _total(host, token, path, {**_scope(project_key, path), **filters})
            if (seen >= want and seen == previous) or time.monotonic() >= deadline:
                break
            previous = seen
            time.sleep(POLL_SECONDS)
        print(f"Indexed {name}: {seen} of {want}")
        if seen < want:
            print(f"::warning::SonarCloud {name} index still behind the analysis after {INDEX_WAIT_SECONDS}s")


def _describe(item: dict) -> str:
    location = item.get("component", "").split(":", 1)[-1]
    if line := item.get("line"):
        location = f"{location}:{line}"
    rule = item.get("rule") or item.get("ruleKey") or item.get("securityCategory", "")
    kind = item.get("type") or item.get("vulnerabilityProbability", "")
    return f"{location} [{rule}] ({kind}) {item.get('message', '')}"


def main() -> int:
    host = os.environ.get("SONAR_HOST_URL") or "https://sonarcloud.io"
    token = os.environ.get("SONAR_TOKEN")
    project_key = os.environ.get("SONAR_PROJECT_KEY")
    if not token or not project_key:
        print("::error::SONAR_TOKEN and SONAR_PROJECT_KEY are required")
        return 2

    _wait_for_index(host, token, project_key)
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
