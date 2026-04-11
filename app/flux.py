import os
import logging
import time
import yaml
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


class FluxManager:
    def __init__(self, config):
        self.config = config
        self.namespace = config.get("flux_namespace", "flux-system")
        self.gitrepo_name = config.get("gitrepo_name", "flux-system")
        self.helmrelease_namespace = config.get("helmrelease_namespace", "flux-system")

        try:
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster config")
        except Exception:
            try:
                k8s_config.load_kube_config()
                logger.info("Loaded local kubeconfig")
            except Exception as e:
                logger.error(f"Could not load kube config: {e}")
                raise

        self.core_v1 = client.CoreV1Api()
        self.custom_objects = client.CustomObjectsApi()

    def update_gitrepository_branch(self, branch_name, dry_run=True):
        logger.info(
            f"Updating GitRepository '{self.gitrepo_name}' to branch '{branch_name}' (dry_run={dry_run})"
        )

        try:
            gitrepo = self.custom_objects.get_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.namespace,
                plural="gitrepositories",
                name=self.gitrepo_name,
            )
        except ApiException as e:
            logger.error(f"Error getting GitRepository: {e}")
            return False

        current_ref = gitrepo.get("spec", {}).get("ref", {})
        logger.info(f"Current ref: {current_ref}")

        patch = {"spec": {"ref": {"branch": branch_name}}}

        if dry_run:
            logger.info(f"[DRY-RUN] Would patch GitRepository with: {patch}")
            return True

        try:
            self.custom_objects.patch_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.namespace,
                plural="gitrepositories",
                name=self.gitrepo_name,
                body=patch,
            )
            logger.info(f"Successfully updated GitRepository to branch '{branch_name}'")
            return True
        except ApiException as e:
            logger.error(f"Error patching GitRepository: {e}")
            return False

    def wait_for_reconciliation(self, timeout_seconds=300):
        logger.info(f"Waiting for Flux reconciliation (timeout={timeout_seconds}s)...")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                kustomization = self.custom_objects.get_namespaced_custom_object(
                    group="kustomize.toolkit.fluxcd.io",
                    version="v1",
                    namespace=self.namespace,
                    plural="kustomizations",
                    name=self.gitrepo_name,
                )

                conditions = kustomization.get("status", {}).get("conditions", [])
                gitrepo = self.custom_objects.get_namespaced_custom_object(
                    group="source.toolkit.fluxcd.io",
                    version="v1",
                    namespace=self.namespace,
                    plural="gitrepositories",
                    name=self.gitrepo_name,
                )
                branch = gitrepo.get("spec", {}).get("ref", {}).get("branch", "unknown")
                kustomization_artifact = kustomization.get("status", {}).get(
                    "artifact", {}
                )
                kustomization_revision = kustomization_artifact.get(
                    "revision", "unknown"
                )
                for cond in conditions:
                    if cond.get("type") == "Ready":
                        if cond.get("status") == "True":
                            logger.info(
                                f"Reconciliation succeeded! Branch: {branch}, SHA: {kustomization_revision}"
                            )
                            return True
                        elif cond.get("status") == "False":
                            logger.error(
                                f"Reconciliation failed: {cond.get('message')}"
                            )
                            return False

                logger.info("Reconciliation in progress...")
                time.sleep(10)

            except ApiException as e:
                logger.error(f"Error checking reconciliation: {e}")
                time.sleep(10)

        logger.warning("Reconciliation timeout")
        return False

    def get_current_version(self):
        try:
            hr = self.custom_objects.get_namespaced_custom_object(
                group="helm.toolkit.fluxcd.io",
                version="v2",
                namespace=self.helmrelease_namespace,
                plural="helmreleases",
                name="traefik",
            )
            version = hr.get("spec", {}).get("chart", {}).get("spec", {}).get("version")
            logger.info(f"Current Traefik version: {version}")
            return version
        except ApiException as e:
            logger.error(f"Error getting HelmRelease: {e}")
            return None

    # def force_helmrelease_reconciliation(self, name="traefik", dry_run=True):
    #     logger.info(f"Force reconciling HelmRelease '{name}' (dry_run={dry_run})")

    #     patch = {"metadata": {"annotations": {"reconcile.fluxcd.io/force": "true"}}}

    #     if dry_run:
    #         logger.info(f"[DRY-RUN] Would patch HelmRelease with: {patch}")
    #         return True

    #     try:
    #         self.custom_objects.patch_namespaced_custom_object(
    #             group="helm.toolkit.fluxcd.io",
    #             version="v2",
    #             namespace=self.namespace,
    #             plural="helmreleases",
    #             name=name,
    #             body=patch,
    #         )
    #         logger.info(
    #             f"Successfully triggered force reconcile on HelmRelease '{name}'"
    #         )
    #         return True
    #     except ApiException as e:
    #         logger.error(f"Error forcing HelmRelease reconciliation: {e}")
    #         return False

    def wait_for_helmrelease_ready(
        self, name="traefik", dry_run=True, timeout_seconds=300
    ):
        logger.info(
            f"Waiting for HelmRelease '{name}' to be ready (dry_run={dry_run}, timeout={timeout_seconds}s)..."
        )

        if dry_run:
            logger.info("[DRY-RUN] Skipping wait for HelmRelease")
            return True

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                hr = self.custom_objects.get_namespaced_custom_object(
                    group="helm.toolkit.fluxcd.io",
                    version="v2",
                    namespace=self.helmrelease_namespace,
                    plural="helmreleases",
                    name=name,
                )

                conditions = hr.get("status", {}).get("conditions", [])
                for cond in conditions:
                    if cond.get("type") == "Ready":
                        if cond.get("status") == "True":
                            version = hr.get("status", {}).get(
                                "lastAppliedRevision", "unknown"
                            )
                            logger.info(
                                f"HelmRelease '{name}' reconciled at version: {version}"
                            )
                            return True
                        elif cond.get("status") == "False":
                            logger.error(
                                f"HelmRelease '{name}' reconciliation failed: {cond.get('message')}"
                            )
                            return False

                logger.info(f"HelmRelease '{name}' reconciliation in progress...")
                time.sleep(10)

            except ApiException as e:
                logger.error(f"Error checking HelmRelease status: {e}")
                time.sleep(10)

        logger.warning(f"HelmRelease '{name}' reconciliation timeout")
        return False

    # def force_and_wait_helmrelease(self, name="traefik", dry_run=True):
    #     logger.info(f"Force and wait for HelmRelease '{name}'")

    #     success = self.force_helmrelease_reconciliation(name=name, dry_run=dry_run)
    #     if not success:
    #         logger.error(f"Failed to trigger force reconcile on HelmRelease '{name}'")
    #         return False

    #     if dry_run:
    #         logger.info("[DRY-RUN] Skipping wait for HelmRelease")
    #         return True

    #     return self.wait_for_helmrelease_ready(name=name)

    # def revert_to_main(self):
    #     main_branch = "main"
    #     logger.info(
    #         f"Reverting GitRepository '{self.gitrepo_name}' to branch '{main_branch}'"
    #     )

    #     patch = {"spec": {"ref": {"branch": main_branch}}}

    #     try:
    #         self.custom_objects.patch_namespaced_custom_object(
    #             group="source.toolkit.fluxcd.io",
    #             version="v1",
    #             namespace=self.namespace,
    #             plural="gitrepositories",
    #             name=self.gitrepo_name,
    #             body=patch,
    #         )
    #         logger.info(
    #             f"Successfully reverted GitRepository to branch '{main_branch}'"
    #         )

    #             logger.info("Waiting for Kustomization to reconcile after revert...")
    #             self.wait_for_reconciliation(timeout_seconds=300)
    #             return True
    #     except ApiException as e:
    #         logger.error(f"Error reverting GitRepository: {e}")
    #         return False

    def force_helmrelease_reconciliation(self, name="traefik"):
        logger.info(f"Force reconciling HelmRelease '{name}'")

        patch = {"metadata": {"annotations": {"reconcile.fluxcd.io/force": "true"}}}

        try:
            self.custom_objects.patch_namespaced_custom_object(
                group="helm.toolkit.fluxcd.io",
                version="v2",
                namespace=self.helmrelease_namespace,
                plural="helmreleases",
                name=name,
                body=patch,
            )
            logger.info(
                f"Successfully triggered force reconcile on HelmRelease '{name}'"
            )
            return True
        except ApiException as e:
            logger.error(f"Error forcing HelmRelease reconciliation: {e}")
            return False

    def fix_helmrelease_with_ai(
        self, name="traefik", namespace=None, opencode_assist=None, max_retries=5
    ):
        if namespace is None:
            namespace = self.helmrelease_namespace

        if opencode_assist is None:
            logger.error("OpencodeAssist not provided")
            return False, "OpencodeAssist not provided"

        custom_objects = self.custom_objects

        for attempt in range(1, max_retries + 1):
            logger.info(f"AI fix attempt {attempt}/{max_retries}")

            try:
                hr = custom_objects.get_namespaced_custom_object(
                    group="helm.toolkit.fluxcd.io",
                    version="v2",
                    namespace=namespace,
                    plural="helmreleases",
                    name=name,
                )
            except ApiException as e:
                logger.error(f"Error getting HelmRelease: {e}")
                return False, f"Error getting HelmRelease: {e}"

            conditions = hr.get("status", {}).get("conditions", [])
            ready = next((c for c in conditions if c.get("type") == "Ready"), None)

            if ready and ready.get("status") == "True":
                version = hr.get("status", {}).get("lastAppliedRevision", "unknown")
                return True, f"HelmRelease Ready (version {version})"

            error_msg = (
                ready.get("message", "Unknown error") if ready else "No Ready condition"
            )
            logger.error(f"HelmRelease error: {error_msg}")

            current_values = hr.get("spec", {}).get("values", {})
            current_values_yaml = yaml.dump(current_values, default_flow_style=False)

            chart_spec = hr.get("spec", {}).get("chart", {}).get("spec", {})
            version = chart_spec.get("version", "unknown")

            fixed = opencode_assist.fix_values(error_msg, current_values_yaml, version)
            if not fixed:
                logger.warning(
                    f"Attempt {attempt}: opencode failed to provide valid fix"
                )
                continue

            commit_msg = (
                f"fix: auto-fix values for Traefik {version} (attempt {attempt})"
            )
            if not opencode_assist.commit_and_push(fixed, commit_msg):
                logger.warning(f"Attempt {attempt}: git commit/push failed")
                continue

            self.force_helmrelease_reconciliation(name)

            if self.wait_for_helmrelease_ready(
                name, dry_run=False, timeout_seconds=300
            ):
                return True, f"Fixed and reconciled on attempt {attempt}"

        return False, f"Failed after {max_retries} attempts"
