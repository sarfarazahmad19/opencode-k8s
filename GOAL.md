# Goal: Fix Traefik HelmRelease values and verify tests pass

## Context
- PR branch: updatecli-traefik-39.0.7
- Target version: 39.0.7
- HelmRelease: traefik in namespace traefik
- Kustomization: flux-system in namespace flux-system
- Git repo path: /datadrive/home/ahmad/git/opencode-k8s
- SSH key path: /home/ahmads/.ssh/id_rsa

## Test Command
uv run pytest tests/ --namespace=traefik --helmrelease-namespace=traefik

## Workflow
1. Check HelmRelease status, wait if reconciling
2. Run tests: if fail, continue
3. Fix flux/HelmRelease.yaml values if needed
4. Commit fix to branch updatecli-traefik-39.0.7, push (use SSH key)
5. Force reconcile:
   - Kustomization: patch with {"reconcile.fluxcd.io/force": "true"}
   - HelmRelease: patch with {"reconcile.fluxcd.io/force": "true"}
6. Wait for HelmRelease Ready=True
7. Re-run tests to verify
8. Write results to app/logs/opencode_result.json with format:
   {"success": true/false, "version": "x.y.z", "test_output": "..."}
