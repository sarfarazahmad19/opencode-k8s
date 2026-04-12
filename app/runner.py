import os
import subprocess
import logging
import yaml
import json
from github import Github

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(config_path=None):
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}")
        return {}

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


TEST_RESULTS_FILE = "/tmp/opencode_test_results.json"


def run_tests(config):
    """Run pytest tests before or after upgrade."""
    logger.info("Running pytest tests...")

    test_dir = os.path.join(os.path.dirname(__file__), "..", "tests")
    if not os.path.exists(test_dir):
        logger.error(f"Tests directory not found: {test_dir}")
        return {"success": False, "output": "", "test_results": []}

    namespace = config.get("test_namespace", "flux-system")

    result = subprocess.run(
        [
            "pytest",
            "-v",
            "--tb=short",
            "--color=yes",
            "-s",
            "--ignore-unknown-dependency",
            f"--namespace={namespace}",
            f"--helmrelease-namespace=traefik",
            test_dir,
        ],
        capture_output=True,
        text=True,
    )

    logger.info(f"Pytest output:\n{result.stdout}")
    if result.stderr:
        logger.warning(f"Pytest stderr:\n{result.stderr}")

    test_results = parse_pytest_output(result.stdout)
    result_dict = {
        "success": result.returncode == 0,
        "output": result.stdout,
        "test_results": test_results,
    }

    with open(TEST_RESULTS_FILE, "w") as f:
        f.write(json.dumps(result_dict))

    return result_dict


def run_before_tests(config):
    """Run tests before upgrade - verify current state is healthy."""
    logger.info("Running pre-upgrade tests...")
    return run_tests(config)


def run_after_tests(config):
    """Run tests after upgrade - verify upgrade was successful."""
    logger.info("Running post-upgrade tests...")
    return run_tests(config)


def parse_pytest_output(output):
    results = []
    lines = output.split("\n")
    for line in lines:
        if "[CHECK]" in line:
            results.append({"description": line.split("[CHECK]")[1].strip()})
    return results


def post_results_to_pr(pr_url, test_result=None, version=None):
    """Post test results to GitHub PR."""
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN not set - cannot post to PR")
        return False

    g = Github(github_token)

    pr_number = pr_url.strip("/").split("/")[-1]
    repo_path = os.environ.get("REPO", "sarfarazahmad19/opencode-k8s")
    repo = g.get_repo(repo_path)

    if test_result is None:
        if os.path.exists(TEST_RESULTS_FILE):
            with open(TEST_RESULTS_FILE, "r") as f:
                test_result = json.loads(f.read())
        else:
            logger.error(f"No test results found at {TEST_RESULTS_FILE}")
            return False

    status = "✅ PASSED" if test_result["success"] else "❌ FAILED"
    version_label = f" (version: {version})" if version else ""

    lines = []
    for test in test_result.get("test_results", []):
        icon = "✅"
        lines.append(f"{icon} {test['description']}")

    test_summary = "\n".join(lines) if lines else "No test results"

    body = f"""## Test Results{version_label}: {status}

**Test Output:**
```
{test_result.get("output", "No output")}
```

### Checks
{test_summary}
"""
    try:
        pr = repo.get_pull(int(pr_number))
        pr.create_issue_comment(body)
        logger.info(f"Posted results to PR #{pr_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to post to PR: {e}")
        return False
