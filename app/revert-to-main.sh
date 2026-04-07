#!/bin/bash
kubectl patch gitrepository/flux-system -n flux-system --type merge -p '{"spec":{"ref":{"branch":"main"}}}' && kubectl annotate helmrelease/traefik -n flux-system reconcile.fluxcd.io/force=true && kubectl rollout status -n flux-system deploy/traefik --timeout=300s
