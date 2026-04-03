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
├── .github/workflows/
│   └── updatecli.yaml          # GitHub Action for auto-update
├── updatecli.yaml              # updatecli configuration
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
updatecli apply --config updatecli.yaml --dry-run
```

The workflow runs on schedule (weekly) or manually via `workflow_dispatch`. It checks for new Traefik helm chart versions and creates a PR if an update is available.
