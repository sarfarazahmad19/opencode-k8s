import pytest
from kubernetes import client


def test_helmrelease_reconciled(
    custom_objects, helmrelease_name="traefik", helmrelease_namespace="traefik"
):
    """Verify HelmRelease is reconciled and target version matches deployed version.

    This test MUST pass for other tests to run.
    """
    hr = custom_objects.get_namespaced_custom_object(
        group="helm.toolkit.fluxcd.io",
        version="v2",
        plural="helmreleases",
        namespace=helmrelease_namespace,
        name=helmrelease_name,
    )

    conditions = hr.get("status", {}).get("conditions", [])
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in conditions
    )

    target_version = hr.get("spec", {}).get("chart", {}).get("spec", {}).get("version")
    deployed_version = hr.get("status", {}).get("lastAttemptedRevision", "")

    assert ready, f"HelmRelease not Ready. Conditions: {conditions}"
    assert deployed_version, "No version in HelmRelease status"
    assert deployed_version == target_version, (
        f"Version mismatch: deployed={deployed_version}, target={target_version}"
    )

    print(f"[CHECK] HelmRelease '{helmrelease_name}' reconciled: {deployed_version}")
