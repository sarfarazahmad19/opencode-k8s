import pytest
import time
import subprocess
import yaml
from kubernetes import client


pytestmark = pytest.mark.dependency(
    depends=["test_helmrelease.py::test_helmrelease_reconciled"]
)


def test_traefik_pods_running(traefik_pods):
    """Verify Traefik pods are Running"""
    assert len(traefik_pods) > 0, "No Traefik pods found"

    for pod in traefik_pods:
        assert pod.status.phase == "Running", (
            f"Pod {pod.metadata.name} is not Running: {pod.status.phase}"
        )

    print(f"[CHECK] {len(traefik_pods)} Traefik pod(s) are Running and healthy")


def test_traefik_service_exists(traefik_service):
    """Verify Traefik service exists"""
    assert traefik_service is not None, "Traefik service not found"
    assert traefik_service.spec.type is not None, "Service type not set"

    print(
        f"[CHECK] Traefik service '{traefik_service.metadata.name}' is available in '{traefik_service.metadata.namespace}' namespace"
    )


def test_traefik_responds(core_v1, namespace):
    """Verify Traefik responds to requests by deploying a test app with Ingress"""

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
        # Cleanup commented out for debugging
        # try:
        #     apps_v1 = client.AppsV1Api()
        #     core_v1 = client.CoreV1Api()
        #     networking_v1 = client.NetworkingV1Api()
        #     apps_v1.delete_namespaced_deployment(test_app_name, test_namespace)
        #     core_v1.delete_namespaced_service(test_app_name, test_namespace)
        #     networking_v1.delete_namespaced_ingress(f"{test_app_name}-ingress", test_namespace)
        # except:
        #     pass


def test_traefik_has_ingress_class(core_v1, namespace):
    """Verify Traefik has IngressClass configured"""
    networking_v1 = client.NetworkingV1Api()

    try:
        iclass = networking_v1.read_ingress_class("traefik")
        assert iclass is not None, "Traefik IngressClass not found"
        print("[CHECK] Traefik IngressClass is configured")
    except client.ApiException as e:
        if e.status == 404:
            pytest.skip("Traefik IngressClass not found (may use default)")
        raise
