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

## Current Status
- ✅ Kind cluster `kind` running
- ✅ FluxCD installed (source, kustomize, helm controllers)
- ✅ GitRepository reconciled from this git repo
- ✅ Kustomization applied
- ✅ HelmRepository + HelmRelease created
- ✅ Dummy secret created
- ✅ Traefik deployed (chart v39.0.2)
- ✅ Updatecli configured for auto-version updates
