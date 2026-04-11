import os
import logging
import subprocess
import yaml
import git as gitpython

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


class OpencodeAssist:
    def __init__(self, repo_path: str, branch: str, ssh_key_path: str):
        self.repo_path = repo_path
        self.branch = branch
        self.ssh_key_path = ssh_key_path

    def get_current_values(
        self, custom_objects_api, helmrelease_name: str, namespace: str
    ) -> str:
        hr = custom_objects_api.get_namespaced_custom_object(
            group="helm.toolkit.fluxcd.io",
            version="v2",
            namespace=namespace,
            plural="helmreleases",
            name=helmrelease_name,
        )
        values = hr.get("spec", {}).get("values", {})
        return yaml.dump(values, default_flow_style=False)

    def build_opencode_prompt(
        self, error_message: str, current_values: str, chart_version: str
    ) -> str:
        return f"""The Traefik HelmRelease failed to reconcile with this error:

{error_message}

The HelmRelease is upgrading to version {chart_version}.
Here are the current values that caused the failure:

{current_values}

Fix the values.yaml to be compatible with version {chart_version}.
Respond ONLY with the corrected YAML values block, no explanations."""

    def fix_values(
        self, error_message: str, current_values: str, chart_version: str
    ) -> dict | None:
        prompt = self.build_opencode_prompt(
            error_message, current_values, chart_version
        )

        try:
            result = subprocess.run(
                ["opencode", "--print"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f"opencode CLI error: {result.stderr}")
                return None

            fixed = yaml.safe_load(result.stdout)
            if fixed and isinstance(fixed, dict):
                logger.info(
                    f"Received fixed values from opencode: {list(fixed.keys())}"
                )
                return fixed
            else:
                logger.warning("opencode output is not valid YAML dict")
        except subprocess.TimeoutExpired:
            logger.warning("opencode invocation timed out")
        except FileNotFoundError:
            logger.error("opencode CLI not found")
        except yaml.YAMLError as e:
            logger.warning(f"YAML parse error: {e}")
        except Exception as e:
            logger.warning(f"opencode invocation failed: {e}")

        return None

    def commit_and_push(self, values: dict, commit_message: str) -> bool:
        os.environ["GIT_SSH_COMMAND"] = (
            f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no"
        )

        try:
            repo = gitpython.Repo(self.repo_path)
        except gitpython.exc.InvalidGitRepositoryError as e:
            logger.error(f"Invalid git repo: {e}")
            return False

        try:
            repo.git.checkout("-B", self.branch, f"origin/{self.branch}")
        except gitpython.exc.GitCommandError:
            try:
                repo.git.checkout("-B", self.branch)
            except gitpython.exc.GitCommandError as e:
                logger.error(f"Failed to checkout branch {self.branch}: {e}")
                return False

        helmrelease_path = os.path.join(self.repo_path, "flux", "HelmRelease.yaml")
        with open(helmrelease_path, "r") as f:
            hr = yaml.safe_load(f)

        hr["spec"]["values"] = values

        with open(helmrelease_path, "w") as f:
            yaml.dump(hr, f, default_flow_style=False, sort_keys=False)

        repo.index.add([helmrelease_path])
        repo.index.commit(commit_message)

        try:
            origin = repo.remotes.origin
            origin.push(refspec=f"refs/heads/{self.branch}:refs/heads/{self.branch}")
            logger.info(f"Committed and pushed: {commit_message}")
            return True
        except gitpython.exc.GitCommandError as e:
            logger.error(f"Git push failed: {e}")
            return False
