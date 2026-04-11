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

## Test Command
uv run pytest tests/ --namespace=traefik --helmrelease-namespace=traefik

## Workflow
1. Check HelmRelease status, wait if reconciling
2. Run tests: if fail, continue
3. Fix flux/HelmRelease.yaml values if needed. You need to make sure the change to values.yaml does not strip away any enabled features.
4. Commit fix to branch updatecli-traefik-39.0.7, push (use SSH key)
5. Force reconcile:
   - Kustomization: patch with {"reconcile.fluxcd.io/force": "true"}
   - HelmRelease: patch with {"reconcile.fluxcd.io/force": "true"}
6. Wait for HelmRelease Ready=True
7. Re-run tests to verify
8. Write results to app/logs/opencode_result.json with format:
   {"success": true/false, "version": "x.y.z", "test_output": "..."}