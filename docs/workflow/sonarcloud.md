# SonarCloud code-quality gate (part of CP3)

Every service in the CI matrix (`.github/workflows/ci.yml`) is analysed by SonarCloud on each pull request
to `main` and each push to `main`. The service's CI job fails when either check fails:

1. **Quality Gate**: the organization's default gate ("Sonar way"). The scanner waits for the result
   (`sonar.qualitygate.wait=true`). This gate judges *new code*: no new issues rated below A, every new
   security hotspot reviewed, at least 80% coverage, no more than 3% duplication.
2. **Findings gate** (`.github/scripts/sonar_findings_gate.py`): fails if the analysed pull request or
   branch has any open **vulnerability**, any **security hotspot** still to review, or any
   **CRITICAL/BLOCKER code smell**. Lower-severity code smells are reported by SonarCloud but do not fail
   the build. On a pull request the API returns the findings SonarCloud reports for that pull request.
   On `main` it returns every open finding in the project.

Coverage comes from the PostgreSQL test run (`pytest --cov=app --cov-report=xml:coverage.xml`), so it
includes the PostgreSQL-only concurrency and migration tests. Migrations are scanned but left out of
coverage.

## One-time setup

| Item | Where | Value |
|---|---|---|
| SonarCloud organization | sonarcloud.io, imported from GitHub | e.g. `msocial123` |
| Projects | One per service; use "Set up a monorepo" with GitHub Actions analysis | key `<organization>_<service>`, e.g. `msocial123_appointment-service` |
| Automatic Analysis | Each project → Administration → Analysis Method | **Off**. CI analysis fails while it is on. |
| `SONAR_TOKEN` | GitHub → Settings → Secrets and variables → Actions → **Secrets** | Token from sonarcloud.io → My Account → Security |
| `SONAR_ORGANIZATION` | GitHub → Settings → Secrets and variables → Actions → **Variables** | Organization key |

When a new service joins the CI matrix, create its SonarCloud project with the same key pattern.
If `SONAR_TOKEN` or `SONAR_ORGANIZATION` is missing, the CI job fails with a clear error instead of
skipping the gate.

## Notifications

No mail credentials are stored in the repository.

- **GitHub** emails workflow results to the person who triggered the run. To get emails for successful
  runs as well as failed ones, go to github.com → Settings → Notifications → System → Actions and turn
  off "Only notify for failed workflows".
- **SonarCloud** sends email when a project's Quality Gate status changes or new issues are assigned to
  you. Set this up under My Account → Notifications for each project. SonarCloud does not email on every
  analysis.

## Handling a failure

Open the SonarCloud link printed by the failed step.

- **Fix code smells and vulnerabilities in code.** Don't suppress them.
- **Review security hotspots in SonarCloud.** Mark each one Safe or Fixed. Record the justification in
  SonarCloud and in the PR.
- **Accepting an issue or marking it a false positive** needs a reviewer's agreement, and the PR must
  record it.
