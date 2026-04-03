import os
import logging
import time
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FluxManager:
    def __init__(self, config):
        self.config = config
        self.namespace = config.get('flux_namespace', 'flux-system')
        self.gitrepo_name = config.get('gitrepo_name', 'flux-system')
        
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster config")
        except Exception:
            try:
                config.load_kube_config()
                logger.info("Loaded local kubeconfig")
            except Exception as e:
                logger.error(f"Could not load kube config: {e}")
                raise

        self.core_v1 = client.CoreV1Api()
        self.custom_objects = client.CustomObjectsApi()

    def update_gitrepository_branch(self, branch_name, dry_run=True):
        logger.info(f"Updating GitRepository '{self.gitrepo_name}' to branch '{branch_name}' (dry_run={dry_run})")
        
        try:
            gitrepo = self.custom_objects.get_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.namespace,
                plural="gitrepositories",
                name=self.gitrepo_name
            )
        except ApiException as e:
            logger.error(f"Error getting GitRepository: {e}")
            return False

        current_ref = gitrepo.get('spec', {}).get('ref', {})
        logger.info(f"Current ref: {current_ref}")

        patch = {
            'spec': {
                'ref': {
                    'branch': branch_name
                }
            }
        }

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
                body=patch
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
                    name=self.gitrepo_name
                )
                
                conditions = kustomization.get('status', {}).get('conditions', [])
                for cond in conditions:
                    if cond.get('type') == 'Ready':
                        if cond.get('status') == 'True':
                            logger.info("Reconciliation succeeded!")
                            return True
                        elif cond.get('status') == 'False':
                            logger.error(f"Reconciliation failed: {cond.get('message')}")
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
                namespace=self.namespace,
                plural="helmreleases",
                name="traefik"
            )
            version = hr.get('spec', {}).get('chart', {}).get('spec', {}).get('version')
            logger.info(f"Current Traefik version: {version}")
            return version
        except ApiException as e:
            logger.error(f"Error getting HelmRelease: {e}")
            return None
