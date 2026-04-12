# Kind + FluxCD Setup Plan

## Overview
Set up a local Kubernetes cluster using kind and manage it with FluxCD GitOps.

## Prerequisites Met
- Docker daemon running
- kubectl available

## Step 1: Install Tools
Created `bin/` directory with:
- `kind` v0.20.0
- `flux` (latest)
- `helm` v3.16.4

## Step 2: Create Kind Cluster
```bash
kind create cluster --name kind
```
- Cluster `kind` created successfully
- kubectl context set to `kind-kind`

## Step 3: Install FluxCD
```bash
flux install --components=source-controller,helm-controller
```
- Installed to `flux-system` namespace
- Components: source-controller, helm-controller

## Step 4: Flux Manifests
Created in `flux/` directory:

| File | Description |
|------|-------------|
| `GitRepository.yaml` | Points to this git repo (HTTPS) |
| `HelmRepository.yaml` | Traefik chart repo |
| `HelmRelease.yaml` | Traefik chart v39.0.2 |
| `kustomization.yaml` | Combines all resources |

## Step 5: Current Status
- Flux controllers running
- GitRepository pending reconciliation (needs credentials or public access)
- HelmRepository created
- HelmRelease created

## Remaining Steps
1. Ensure git repo is accessible (public or add credentials)
2. Reconcile GitRepository: `flux reconcile source git flux-system`
3. Verify Traefik deployment: `flux get all`, `kubectl get hr -A`

## Usage
```bash
# Check cluster
kubectl cluster-info --context kind-kind

# Check flux
./bin/flux get all

# Check traefik
kubectl get hr -A -n flux-system
kubectl get pods -n traefik
```

## Files Created
- `bin/kind` - kind binary
- `bin/flux` - flux binary  
- `bin/helm` - helm binary
- `flux/GitRepository.yaml` - Git source
- `flux/HelmRepository.yaml` - Helm repo source
- `flux/HelmRelease.yaml` - Traefik release
- `flux/kustomization.yaml` - Kustomize config

## Step 6: Updatecli (Auto-update)
Added updatecli for automated Traefik version updates:

| File | Description |
|------|-------------|
| `.github/workflows/updatecli.yaml` | GitHub Action workflow |
| `updatecli.yaml` | updatecli configuration |

### updatecli Configuration
- `scms`: Defines GitHub connection (token, repo, branch)
- `scmid`: Creates commits/PRs using the SCM
  - `pullRequest`: PR title, body, labels
  - `commitmessage`: Commit message template
- `sources`: Fetches Traefik chart versions (semver filter `39.*`)
- `targets`: Updates HelmRelease.yaml with new version

## Current Status
- ✅ Kind cluster `kind` running
- ✅ FluxCD installed (source, kustomize, helm controllers)
- ✅ GitRepository reconciled from this git repo
- ✅ Kustomization applied
- ✅ HelmRepository + HelmRelease created
- ✅ Dummy secret created
- ✅ Traefik deployed (chart v39.0.2)
- ✅ Updatecli configured for auto-version updates

---

## Proof of Concept: Breaking Changes (v38 → v39)

### Objective
Demonstrate that upgrading between Traefik chart versions with breaking changes requires manual values.yaml adjustments.

### Breaking Change Identified
**Ports Configuration (v38 → v39):** HTTP options now require explicit `http` nesting level (PR #1603)

v38 format:
```yaml
ports:
  web:
    http:
      # no nesting needed
```

v39 format:
```yaml
ports:
  web:
    http:
      http:
        # explicit nesting required
```

### Execution Steps

1. **Deploy v38.0.2**
   - Update `flux/HelmRelease.yaml` to version `38.0.2`
   - Create `flux/values.yaml` with v38-compatible values
   - Reconcile Flux

2. **Verify v38 deployment**

3. **Upgrade to v39.0.7**
   - Update version to `39.0.7`
   - Add breaking change fix to values.yaml (extra `http` nesting)
   - Reconcile Flux

4. **Document results**
   - v38 works without changes
   - v39 upgrade fails without values.yaml fix
   - v39 upgrade succeeds after applying fix

---

## Automated Testing Pipeline

### Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  updatecli PR   │────▶│  Python Poller      │────▶│  GitRepository  │
│  (label: traefik)│     │  (every 5 min)      │     │  (update branch)│
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                                            │
                                                            ▼
                         ┌─────────────────┐     ┌─────────────────┐
                         │  pytest tests   │◀────│  Flux reconcile │
                         │  (ingress test) │     │  (auto-trigger) │
                         └─────────────────┘     └─────────────────┘
                                │
                                ▼
                         ┌─────────────────┐
                         │  GitHub PR      │
                         │  (comment only) │
                         └─────────────────┘
```

### Execution Flow

1. **updatecli** creates PR with `traefik` label → version bump
2. **Poller** (every 5 min) detects PR with `traefik` label
3. **Poller** updates existing `GitRepository` to point to PR branch
4. **Flux** reconciles automatically → deploys new version
5. **Poller** runs pytest → verifies Traefik ingress works
6. **Post PR comment:**
   - **Dry-run (default):** Just log results
   - **Normal (--no-dry-run):** Post test results as PR comment

### Execution Modes

| Mode | Command | Behavior |
|------|---------|----------|
| **Default (dry-run)** | `uv run python main.py` | Polls & logs, no GitHub comment |
| **K8s Pod** | Runs in cluster | Polls every 5 min, posts to PR |
| **Local** | `uv run python main.py --run-once` | Single run |
| **Explicit dry-run** | `uv run python main.py --dry-run` | Log only, no comment |
| **Force comment** | `uv run python main.py --no-dry-run --run-once` | Posts to PR |

### Files Created

```
.
├── app/
│   ├── main.py              # Poller entrypoint (CLI + scheduler)
│   ├── poller.py            # GitHub PR polling (multi-label support)
│   ├── flux.py              # GitRepository/Flux management
│   ├── config.yaml          # Configuration (labels: updatecli, traefik)
│   ├── pyproject.toml       # UV Python project config
│   ├── requirements.txt     # Python dependencies (legacy)
│   ├── .venv/               # UV virtual environment
├── tests/
│   ├── conftest.py         # K8s client fixture
│   └── test_traefik_ingress.py  # Version-agnostic ingress tests
├── flux/
│   └── ...                 # (already exists)
├── .github/workflows/
│   └── updatecli.yaml      # (already exists)
└── updatecli.yaml          # updatecli config with scmid + PR
```

### Python Dependencies (UV)

#### Using UV (Recommended)
```bash
cd app
uv sync
uv run python main.py --run-once
uv run python main.py --no-dry-run --run-once
```

#### Using requirements.txt (Legacy)
```bash
pip install -r app/requirements.txt
python app/main.py --run-once
```

| Dependency | Purpose |
|------------|---------|
| pygithub | GitHub API client |
| kubernetes | K8s client for Flux |
| pytest | Testing framework |
| schedule | Job scheduling |
| click | CLI framework |
| pyyaml | Config parsing |

### Multi-Label Polling

The poller filters PRs that have **both** `updatecli` AND `traefik` labels (AND logic):

```yaml
# app/config.yaml
labels:
  - updatecli
  - traefik
```

This ensures only updatecli-created PRs for Traefik are processed.

---

## Version Detection Fixes

### Problem
When running with `--no-opencode-run`, target version was incorrectly reported as the current version (e.g., 38.0.2 instead of 39.0.7). This was due to a race condition where `get_current_version()` was called before Flux had actually attempted the new version.

### Root Cause
- `get_current_version()` used `.spec.chart.spec.version` - the target version from the spec
- But after updating GitRepository, the HelmRelease spec hasn't been updated yet
- `status.lastAttemptedRevision` might still show the old version during reconciliation

### Solution: Wait for Generation Increment

1. **Track generation before update**: Added `get_current_version_with_generation()` method that returns `(version, lastAttemptedGeneration)` tuple

2. **Wait for generation to increment**: Added `wait_for_generation_increment()` method that polls until `status.lastAttemptedGeneration` increments from the previous value

3. **Enhanced logging**: Now logs generation in all key places:
   - `get_current_version()` - logs `gen=`, `status=`, `spec=`
   - `wait_for_helmrelease_ready()` - logs `gen=`
   - `fix_helmrelease_with_ai()` - logs `gen=`

### Code Changes

**app/flux.py**:
- `get_current_version()`: Uses `status.lastAttemptedRevision` first, falls back to `spec.chart.spec.version`
- `get_current_version_with_generation()`: Returns tuple with version + generation
- `wait_for_generation_increment()`: Waits for generation to increment

**app/main.py**:
- Uses `get_current_version_with_generation()` to capture generation before update
- Calls `wait_for_generation_increment()` after reconciliation, before getting target version
