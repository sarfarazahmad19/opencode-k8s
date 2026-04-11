## Variables
- software_name: traefik
- current_version: 38.0.2
- target_version: 39.0.7
- pr_branch: updatecli-traefik-39.0.7
- helmrelease_name: traefik
- helmrelease_namespace: traefik
- gitrepo_name: flux-system
- flux_namespace: flux-system
- repo_path: /datadrive/home/ahmad/git/opencode-k8s
- ssh_key_path: /home/ahmads/.ssh/id_rsa
- k8s_context: kind-flux-cluster
- dry_run: true

## Context
- Software: traefik
- Current (from) version: 38.0.2
- Target (to) version: 39.0.7
- PR branch: updatecli-traefik-39.0.7
- HelmRelease: traefik in namespace traefik
- Kustomization: flux-system in namespace flux-system
- Git repo path: /datadrive/home/ahmad/git/opencode-k8s
- SSH key path: /home/ahmads/.ssh/id_rsa
- Kubernetes context: kind-flux-cluster
- Test coverage: All functionality is covered by the test suite in tests/
- Dry-run mode: true

## Test Command
uv run pytest tests/ --namespace=traefik --helmrelease-namespace=traefik

## Workflow
1. Check HelmRelease status, wait if reconciling
2. Run tests: if fail, continue
3. Fix flux/HelmRelease.yaml values if needed. You need to make sure the change to values.yaml does not strip away any enabled features.
4. If dry_run is true, do NOT commit or push. Just log what changes would be made.
5. If dry_run is false, commit fix to branch updatecli-traefik-39.0.7, push (use SSH key)
6. If dry_run is false, force reconcile:
   - Kustomization: patch with {"reconcile.fluxcd.io/force": "true"}
   - HelmRelease: patch with {"reconcile.fluxcd.io/force": "true"}
7. If dry_run is false, wait for HelmRelease Ready=True
8. If dry_run is false, re-run tests to verify
9. Write results to app/logs/opencode_result.json with format:
   {"success": true/false, "version": "x.y.z", "test_output": "..."}
