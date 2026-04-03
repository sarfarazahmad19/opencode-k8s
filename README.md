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
