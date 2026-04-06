# Python App (Traefik Poller) - Context Document

## Overview

The Python app is a GitOps testing automation tool that:
1. Polls GitHub for PRs with specific labels (`updatecli` + `traefik`)
2. Updates FluxCD to reconcile from the PR branch
3. Runs tests to verify the Traefik upgrade works
4. Posts test results back to the GitHub PR

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  updatecli PR   │────▶│  Python Poller       │────▶│  GitRepository  │
│  (label: traefik)│     │  (every 5 min)       │     │  (update branch)│
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                                              │
                                                              ▼
                          ┌─────────────────┐     ┌─────────────────┐
                          │  pytest tests   │◀────│  HelmRelease    │
                          │  (ingress test) │     │  (force reconcile)
                          └─────────────────┘     └─────────────────┘
                                 │
                                 ▼
                          ┌─────────────────┐
                          │  GitHub PR      │
                          │  (comment only) │
                          └─────────────────┘
```

## Components

### `app/main.py`
- Entry point with CLI (click)
- Config loading (YAML + env vars)
- Poll scheduling (schedule library)
- Test execution (pytest subprocess)
- PR comment posting (PyGithub)

### `app/poller.py`
- GitHub API client (PyGithub)
- Multi-label PR filtering (AND logic)
- Tracks processed PRs in memory

### `app/flux.py`
- Kubernetes client (kubernetes library)
- GitRepository branch updates
- Kustomization reconciliation status
- HelmRelease force-reconcile + status

### `app/config.yaml`
```yaml
github_token: ""
repo: "sarfarazahmad19/opencode-k8s"
labels:
  - updatecli
  - traefik
flux_namespace: "flux-system"
gitrepo_name: "flux-system"
test_namespace: "flux-system"
poll_interval: 300
```

## Reconciliation Flow

### Current Flow
```
1. Update GitRepository spec.ref.branch to PR branch
2. Wait for Kustomization Ready=True
3. Assume HelmRelease reconciled automatically
4. Get version from HelmRelease status
5. Run tests
```

### Improved Flow (with force-reconcile)
```
1. Update GitRepository spec.ref.branch to PR branch
2. Wait for Kustomization Ready=True (retry once if fails)
3. Patch HelmRelease annotation: reconcile.fluxcd.io/force=true
4. Wait for HelmRelease Ready=True (retry once if fails)
5. Get version from HelmRelease status
6. Run tests
```

## Verification Strategy

### Kustomization Status
- Check `.status.conditions` for `Ready: True`
- Retry once if fails

### HelmRelease Status
- Check `.status.conditions` for `Ready: True`
- Check `.status.lastAppliedRevision` for version (e.g., "39.0.7")
- Retry once if fails

### Silent March On
- If both Kustomization and HelmRelease retries fail:
  - Log warning at ERROR level
  - Continue anyway (run tests anyway)
  - Post results to PR (tests may fail if version didn't update)

## Usage

### Local Development
```bash
cd app
uv sync
source ../../.github-token
uv run python main.py --run-once
uv run python main.py --no-dry-run --run-once
```

### In Cluster
```bash
# As a cron job or sidecar
# env: GITHUB_TOKEN, POLL_INTERVAL=300
python main.py --no-dry-run
```

## Dependencies

| Package | Purpose |
|---------|---------|
| pygithub | GitHub API |
| kubernetes | K8s client |
| pytest | Testing |
| schedule | Job scheduling |
| click | CLI framework |
| pyyaml | Config parsing |

Managed via `uv` - see `app/pyproject.toml`.

## Key Files

```
app/
├── main.py              # Entry point
├── poller.py            # GitHub PR polling
├── flux.py              # FluxCD K8s operations
├── config.yaml          # Configuration
├── pyproject.toml       # UV project config
└── .venv/               # Virtual environment (generated)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | - | GitHub PAT (required) |
| `LABELS` | `updatecli,traefik` | Comma-separated labels |
| `POLL_INTERVAL` | `300` | Poll interval in seconds |
| `FLUX_NAMESPACE` | `flux-system` | Flux namespace |
| `TEST_NAMESPACE` | `flux-system` | Test namespace |

## Test Execution

- **Command**: `pytest -v --tb=short --namespace={namespace} {test_dir}`
- **Test directory**: `../tests` (relative to `app/`)
- **Namespace**: `flux-system` (from config)
- **Test files**: `tests/test_traefik_ingress.py`
- **Result**: Pass/fail determines PR comment status

### PR Comment Format

```markdown
## Traefik Upgrade Test Results ✅/❌

**Version:** {version_from} → {version_to}

**Timestamp:** {ISO timestamp}

```
{test_output}
```

**Status:** All tests passed / Tests failed
```

## Processed PRs State

- **Current**: In-memory only (`processed_prs` set in Poller class)
- **Issue**: State lost on app restart - same PR could be processed twice
- **Future**: Could persist to file/Redis for production

## Configuration (Hardcoded)

| Item | Current Value | Should be Configurable? |
|------|---------------|------------------------|
| HelmRelease name | `traefik` | Yes (in config.yaml) |
| Kustomization name | `flux-system` | Yes (gitrepo_name) |
| Kustomization timeout | 300s | Maybe |
| HelmRelease timeout | 300s | Maybe |
| Test directory | `../tests` | No (relative is fine) |

## Timeout Values

| Operation | Timeout | Notes |
|-----------|---------|-------|
| Kustomization reconciliation | 300s | Retry once if fails |
| HelmRelease reconciliation | 300s | Retry once if fails |
| Poll interval | 300s (5 min) | Configurable |
| Test execution | No timeout | Let pytest decide |

## Logging

- **Level**: INFO (configurable via standard logging)
- **Format**: `%(asctime)s - %(levelname)s - %(message)s`
- **Output**: stdout/stderr
- **Log entries**:
  - Config loading
  - GitHub API calls
  - Kustomization/HelmRelease status
  - Test results
  - Errors (ERROR level)

## Post-Test Actions

**Current behavior** (after tests run):
1. Post test results as PR comment
2. Mark PR as processed (in-memory)
3. Wait for next poll cycle

**Potential future actions**:
- Add label to PR (e.g., `tested`)
- Close PR after merge
- Trigger additional CI checks

## Next Steps (Enhancements)

1. Persist processed PRs to file (avoid reprocessing on restart)
2. Make HelmRelease name configurable
3. Add configurable timeout values
4. Add label management (add `tested` label after success)
5. Handle merge/close events
6. Add metrics/monitoring
7. Deploy as K8s CronJob or sidecar