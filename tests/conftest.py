import os
import pytest
import subprocess
import yaml
from kubernetes import client, config


@pytest.fixture(scope="session", autouse=True)
def sync_helmrelease():
    """Force sync HelmRelease before tests run - fire and forget"""
    try:
        subprocess.Popen(
            [
                "./bin/flux",
                "reconcile",
                "helmrelease",
                "traefik",
                "-n",
                "traefik",
                "--force",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def pytest_addoption(parser):
    parser.addoption(
        "--namespace",
        action="store",
        default="traefik",
        help="Namespace where Traefik is deployed",
    )
    parser.addoption(
        "--helmrelease", action="store", default="traefik", help="HelmRelease name"
    )
    parser.addoption(
        "--helmrelease-namespace",
        action="store",
        default="traefik",
        help="HelmRelease namespace",
    )


@pytest.fixture(scope="session")
def kubeconfig():
    try:
        config.load_incluster_config()
    except Exception:
        try:
            config.load_kube_config()
        except Exception as e:
            pytest.skip(f"Could not load kubeconfig: {e}")

    return config


@pytest.fixture(scope="session")
def core_v1(kubeconfig):
    return client.CoreV1Api()


@pytest.fixture(scope="session")
def custom_objects(kubeconfig):
    return client.CustomObjectsApi()


@pytest.fixture(scope="session")
def namespace(request):
    return request.config.getoption("--namespace")


@pytest.fixture(scope="session")
def helmrelease_name(request):
    return request.config.getoption("--helmrelease")


@pytest.fixture(scope="session")
def helmrelease_namespace(request):
    return request.config.getoption("--helmrelease-namespace")


@pytest.fixture(scope="session")
def traefik_service(core_v1, namespace):
    """Get Traefik service"""
    try:
        return core_v1.read_namespaced_service("traefik", namespace)
    except client.ApiException as e:
        if e.status == 404:
            pytest.fail(f"Traefik service not found in namespace {namespace}")
        raise


@pytest.fixture(scope="session")
def traefik_pods(core_v1, namespace):
    """Get Traefik pods"""
    pods = core_v1.list_namespaced_pod(
        namespace=namespace, label_selector="app.kubernetes.io/name=traefik"
    )
    return pods.items
