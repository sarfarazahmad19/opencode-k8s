# PyTest Test Plan

## Overview

This document describes the automated testing infrastructure for validating Traefik Helm releases against breaking changes.

## Test Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  updatecli PR   │────▶│  Python Poller      │────▶│  Flux reconcile │
│  (version bump) │     │  (runs pytest)      │     │  (deploys)      │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                 │
                                 ▼
                          ┌─────────────────┐
                          │  pytest tests   │
                          │  - helmrelease  │
                          │  - ingress      │
                          └─────────────────┘
                                 │
                                 ▼
                          ┌─────────────────┐
                          │  GitHub PR      │
                          │  (comment)      │
                          └─────────────────┘
```

## Test Files

### tests/test_helmrelease.py

Validates HelmRelease reconciliation status:

```python
@pytest.mark.dependency(scope="session")
def test_helmrelease_reconciled(
    custom_objects, helmrelease_name="traefik", helmrelease_namespace="traefik"
):
    """Verify HelmRelease is reconciled and target version matches deployed version.
    
    This test MUST pass for other tests to run.
    """
```

**Checks:**
1. HelmRelease has `Ready: True` condition
2. Target version (`.spec.chart.spec.version`) matches deployed version (`.status.lastAttemptedRevision`)

**Breaking Change Detection:**
- If version bump introduces breaking values changes → HelmRelease fails schema validation
- Test fails → dependent tests skipped → PR needs manual fix

### tests/test_traefik_ingress.py

Validates Traefik functionality after HelmRelease is ready:

| Test | Validates |
|------|-----------|
| `test_traefik_pods_running` | Pods are in Running state |
| `test_traefik_service_exists` | Service exists and has type |
| `test_traefik_responds` | Traefik routes HTTP traffic via Ingress |
| `test_traefik_has_ingress_class` | IngressClass "traefik" exists |

### tests/conftest.py

Pytest fixtures and configuration:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `sync_helmrelease` | session, autouse | Force Flux reconcile before tests (fire-and-forget) |
| `kubeconfig` | session | Load K8s config |
| `core_v1` | session | CoreV1Api client |
| `custom_objects` | session | CustomObjectsApi client |
| `namespace` | session | Get from CLI arg (default: traefik) |
| `helmrelease_name` | session | HelmRelease name (default: traefik) |
| `helmrelease_namespace` | session | HelmRelease namespace (default: traefik) |
| `traefik_service` | session | Get Traefik service |
| `traefik_pods` | session | Get Traefik pods |

## Running Tests

### Basic Usage

```bash
uv run pytest tests/
```

### With Custom Namespace

```bash
uv run pytest tests/ --namespace=traefik
```

### Verbose Output

```bash
uv run pytest tests/ -v
```

### Show Skip Reasons

```bash
uv run pytest tests/ -v -rs
```

## Configuration

### pyproject.toml

```toml
[project]
name = "traefik-tests"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "pytest>=7.0.0",
    "pytest-dependency>=0.5.0",
    "kubernetes>=28.0.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --ignore-unknown-dependency"
```

**Note:** `--ignore-unknown-dependency` is critical - it allows dependent tests to run even when the parent test result isn't registered (a known pytest-dependency issue with cross-module dependencies).

## Breaking Change Validation

### Test Flow

1. **updatecli** bumps version (e.g., 38.0.2 → 39.0.7)
2. **Flux** reconciles → deploys new version
3. **sync_helmrelease** fixture ensures HelmRelease is synced
4. **test_helmrelease_reconciled** runs:
   - If values incompatible → HelmRelease fails → test FAILS
   - If values compatible → HelmRelease succeeds → test PASSES
5. **Dependent tests** run only if helmrelease test passes

### Example: v38 → v39 redirections Breaking Change

| Version | Values Format | HelmRelease | Test Result |
|---------|---------------|-------------|-------------|
| 38.0.2 | `redirections.entryPoint` | ✅ Ready | ✅ PASS |
| 39.0.7 | `redirections.entryPoint` (v38 format) | ❌ Failed | ❌ FAIL |
| 39.0.7 | `http.redirections.entryPoint` (v39 format) | ✅ Ready | ✅ PASS |

### Detected Error

```
AssertionError: HelmRelease not Ready. 
Conditions: [{'type': 'Ready', 'status': 'False', 
  'reason': 'UpgradeFailed', 
  'message': "values don't meet the specifications of the schema(s): 
traefik:\n- ports.web: Additional property redirections is not allowed"}]
```

## Identified Breaking Changes

### 1. Ports Configuration (v38 → v39)

**Source:** https://github.com/traefik/traefik-helm-chart/pull/1603

HTTP options now require explicit `http` nesting level:

```yaml
# v38 (works in v38, fails in v39)
ports:
  web:
    redirections:
      entryPoint:
        to: websecure
        scheme: https

# v39 (works in v39)
ports:
  web:
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
```

### 2. Traefik Hub (v39+)

v39 supports **only** Traefik Hub v3.19.0+. CRDs must be upgraded first.

### 3. Encoded Characters (v39+)

Allowed by default in Traefik v3.6.7+ (security opt-in).

## Future Enhancements

1. **Version-specific tests** - Add expected version parameter to validate exact version
2. **Multiple HelmReleases** - Support testing multiple releases
3. **Pre/post hooks** - Add setup/teardown for test resources
4. **Test parallelization** - Run independent tests in parallel
5. **Detailed reporting** - HTML test reports
6. **Slack/Discord notifications** - Alert on test failures
