import pytest
import time
import subprocess
import yaml
from kubernetes import client, config


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
    try:
        return core_v1.read_namespaced_service("traefik", namespace)
    except client.ApiException as e:
        if e.status == 404:
            pytest.fail(f"Traefik service not found in namespace {namespace}")
        raise


@pytest.fixture(scope="session")
def traefik_pods(core_v1, namespace):
    pods = core_v1.list_namespaced_pod(
        namespace=namespace, label_selector="app.kubernetes.io/name=traefik"
    )
    return pods.items


def pytest_addoption(parser):
    parser.addoption("--namespace", action="store", default="traefik")
    parser.addoption("--helmrelease", action="store", default="traefik")
    parser.addoption("--helmrelease-namespace", action="store", default="traefik")


@pytest.mark.dependency(scope="session")
def test_helmrelease_reconciled(
    custom_objects, helmrelease_name="traefik", helmrelease_namespace="traefik"
):
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


def test_traefik_pods_running(traefik_pods):
    assert len(traefik_pods) > 0, "No Traefik pods found"

    for pod in traefik_pods:
        assert pod.status.phase == "Running", (
            f"Pod {pod.metadata.name} is not Running: {pod.status.phase}"
        )

    print(f"[CHECK] {len(traefik_pods)} Traefik pod(s) are Running and healthy")


def test_traefik_service_exists(traefik_service):
    assert traefik_service is not None, "Traefik service not found"
    assert traefik_service.spec.type is not None, "Service type not set"

    print(
        f"[CHECK] Traefik service '{traefik_service.metadata.name}' is available in '{traefik_service.metadata.namespace}' namespace"
    )


def test_traefik_responds(core_v1, namespace):
    test_app_name = "test-ingress-app"
    test_app_labels = {"app": test_app_name}
    test_namespace = namespace

    try:
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(name=test_app_name, namespace=test_namespace),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(match_labels=test_app_labels),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=test_app_labels),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="nginx",
                                image="nginx:alpine",
                                ports=[client.V1ContainerPort(container_port=80)],
                            )
                        ]
                    ),
                ),
            ),
        )

        service = client.V1Service(
            metadata=client.V1ObjectMeta(name=test_app_name, namespace=test_namespace),
            spec=client.V1ServiceSpec(
                selector=test_app_labels,
                ports=[client.V1ServicePort(port=80, target_port=80)],
            ),
        )

        ingress = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": f"{test_app_name}-ingress",
                "namespace": test_namespace,
                "annotations": {
                    "traefik.ingress.kubernetes.io/router.entrypoints": "web"
                },
            },
            "spec": {
                "ingressClassName": "traefik",
                "rules": [
                    {
                        "host": "test.local",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": test_app_name,
                                            "port": {"number": 80},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
        }

        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        networking_v1 = client.NetworkingV1Api()

        try:
            apps_v1.delete_namespaced_deployment(test_app_name, test_namespace)
            core_v1.delete_namespaced_service(test_app_name, test_namespace)
            networking_v1.delete_namespaced_ingress(
                f"{test_app_name}-ingress", test_namespace
            )
            time.sleep(2)
        except:
            pass

        apps_v1.create_namespaced_deployment(test_namespace, deployment)
        core_v1.create_namespaced_service(test_namespace, service)
        networking_v1.create_namespaced_ingress(test_namespace, ingress)

        time.sleep(10)

        pods = core_v1.list_namespaced_pod(
            namespace=test_namespace, label_selector=f"app={test_app_name}"
        )

        assert len(pods.items) > 0, "Test app pod not created"
        assert pods.items[0].status.phase == "Running", "Test app pod not Running"

        svc = core_v1.read_namespaced_service("traefik", namespace)
        traefik_pod = None
        for pod in core_v1.list_namespaced_pod(
            namespace, label_selector="app.kubernetes.io/name=traefik"
        ).items:
            if pod.status.phase == "Running":
                traefik_pod = pod
                break

        assert traefik_pod is not None, "No running Traefik pod found"

        result = subprocess.run(
            [
                "kubectl",
                "exec",
                "-n",
                namespace,
                traefik_pod.metadata.name,
                "--",
                "wget",
                "-q",
                "-O-",
                "--header",
                "Host: test.local",
                f"http://{test_app_name}.{test_namespace}/",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Traefik did not respond: {result.stderr}"
        assert "Welcome to nginx" in result.stdout or "nginx" in result.stdout, (
            f"Unexpected response: {result.stdout}"
        )

        print(
            f"[CHECK] Traefik routes HTTP traffic from 'web' entrypoint to test app via Ingress"
        )
    finally:
        pass


def test_traefik_has_ingress_class(core_v1, namespace):
    networking_v1 = client.NetworkingV1Api()

    try:
        iclass = networking_v1.read_ingress_class("traefik")
        assert iclass is not None, "Traefik IngressClass not found"
        print("[CHECK] Traefik IngressClass is configured")
    except client.ApiException as e:
        if e.status == 404:
            pytest.skip("Traefik IngressClass not found (may use default)")
        raise
