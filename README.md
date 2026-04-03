# Kind + FluxCD GitOps Setup

Local Kubernetes cluster managed with FluxCD GitOps.

## Quick Start

### Prerequisites
- Docker
- Kind
- kubectl

### Setup

```bash
# Create kind cluster
./bin/kind create cluster --name kind

# Install Flux
./bin/flux install --components=source-controller,kustomize-controller,helm-controller

# Apply Flux manifests
kubectl apply -f flux/GitRepository.yaml
kubectl apply -f flux/flux-kustomization.yaml
```

## Usage

```bash
# Check cluster
kubectl cluster-info --context kind-kind

# Check Flux status
./bin/flux get all -n flux-system

# Check pods
k get pods -n flux-system

# Check Traefik
k get hr -n flux-system
k get svc -n flux-system
```

## Flux Resources

| Resource | Description |
|----------|-------------|
| `GitRepository/flux-system` | Source for this git repo |
| `HelmRepository/traefik` | Traefik Helm chart repo |
| `HelmRelease/traefik` | Traefik deployment (chart v39.0.2) |
| `Secret/dummy-secret` | Dummy secret for testing (base64 encoded) |
| `Kustomization/flux-system` | Orchestrates reconciliation |

## Directory Structure

```
.
├── bin/              # kind, flux, helm binaries
├── flux/
│   ├── GitRepository.yaml      # Git source
│   ├── HelmRepository.yaml     # Helm repo source
│   ├── HelmRelease.yaml        # Traefik release
│   ├── secret.yaml             # Dummy secret
│   ├── flux-kustomization.yaml # Flux Kustomization CRD
│   └── kustomization.yaml      # Kustomize config
├── app/
│   ├── main.py              # Poller entrypoint
│   ├── poller.py            # GitHub PR polling
│   ├── flux.py              # Flux management
│   ├── config.yaml          # Configuration
│   ├── requirements.txt    # Python dependencies
│   └── manifests/
│       └── deployment.yaml  # K8s deployment
├── tests/
│   ├── conftest.py         # K8s client fixture
│   └── test_traefik_ingress.py  # Ingress tests
├── .github/workflows/
│   └── updatecli.yaml      # GitHub Action for auto-update
├── updatecli.yaml          # updatecli configuration
├── .gitignore
├── PLAN.md
└── README.md
```

## Troubleshooting

```bash
# Reconcile manually
./bin/flux reconcile kustomization flux-system -n flux-system

# View logs
k logs -n flux-system -l app.kubernetes.io/part-of=flux
```

## Updatecli (Auto-update Traefik)

This repo uses [updatecli](https://www.updatecli.io/) to automatically propose PRs for newer Traefik helm chart versions.

### Files
- `.github/workflows/updatecli.yaml` - GitHub Action workflow
- `updatecli.yaml` - updatecli configuration

### Usage
```bash
# Trigger manually via GitHub Action or:
./bin/updatecli apply --config updatecli.yaml --push=false
```

The workflow runs manually via `workflow_dispatch`. It creates PRs with label `traefik`.

## Traefik Poller (Automated Testing)

Python app that polls GitHub for PRs with label `traefik`, triggers Flux reconciliation, and runs ingress tests.

### Architecture

```
updatecli PR (label: traefik)
        ↓
    Poller (every 5 min)
        ↓
    GitRepository → PR branch
        ↓
    Flux reconcile
        ↓
    pytest tests
        ↓
    PR comment (test results)
```

### Files

```
app/
├── main.py              # Poller entrypoint (CLI + scheduler)
├── poller.py            # GitHub PR polling (every 5 min)
├── flux.py              # GitRepository/Flux management
├── config.yaml          # Configuration
├── requirements.txt    # Python dependencies
├── manifests/
│   └── deployment.yaml # K8s deployment manifest
tests/
├── conftest.py         # K8s client fixture
└── test_traefik_ingress.py  # Version-agnostic ingress tests
```

### Execution Modes

| Mode | Command | Behavior |
|------|---------|----------|
| **Default (dry-run)** | `python app/main.py` | Polls & logs, no GitHub comment |
| **K8s Pod** | `kubectl apply -f app/manifests/` | Polls every 5 min, posts to PR |
| **Local** | `python app/main.py --run-once` | Single run |
| **Explicit dry-run** | `python app/main.py --dry-run` | Log only, no comment |
| **Force comment** | `python app/main.py --no-dry-run` | Posts to PR |

### Running Locally

```bash
# Install dependencies
pip install -r app/requirements.txt

# Set GitHub token
export GITHUB_TOKEN=ghp_xxx

# Run once (dry-run default)
python app/main.py --run-once

# Run with comments
python app/main.py --run-once --no-dry-run
```

### Running in K8s

```bash
# Create namespace and apply manifests
kubectl apply -f app/manifests/deployment.yaml
```

### Tests

The pytest tests are version-agnostic and verify:
- Traefik pods are Running
- Traefik service exists
- Traefik routes traffic to a test app via Ingress
