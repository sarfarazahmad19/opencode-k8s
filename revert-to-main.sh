#!/bin/bash
# Revert GitRepository to main branch and reconcile

kubectl patch gitrepository flux-system -n flux-system --type merge -p '{"spec":{"ref":{"branch":"main"}}}' && flux reconcile source git flux-system -n flux-system && flux reconcile kustomization flux-system -n flux-system && flux reconcile helmrelease traefik -n traefik