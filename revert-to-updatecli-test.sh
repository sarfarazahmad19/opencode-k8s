#!/bin/bash
# Revert GitRepository to updatecli test branch and reconcile

kubectl patch gitrepository flux-system -n flux-system --type merge -p '{"spec":{"ref":{"branch":"updatecli_main_25cae498eee0a0f01f59966ddce3cf228aa546404e37b9f9f67411da612957f1"}}}' && flux reconcile source git flux-system -n flux-system && flux reconcile kustomization flux-system -n flux-system && flux reconcile helmrelease traefik -n traefik