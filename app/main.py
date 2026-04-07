import os
import sys
import logging
import time
import schedule
import yaml
import click
import subprocess
import signal
from datetime import datetime

from poller import Poller
from flux import FluxManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(config_path=None):
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}")
        return {
            "github_token": os.environ.get("GITHUB_TOKEN"),
            "repo": os.environ.get("REPO", "sarfarazahmad19/opencode-k8s"),
            "labels": os.environ.get("LABELS", "updatecli,traefik").split(","),
            "label": os.environ.get("LABEL", "traefik"),
            "flux_namespace": os.environ.get("FLUX_NAMESPACE", "flux-system"),
            "gitrepo_name": os.environ.get("GITREPO_NAME", "flux-system"),
            "poll_interval": int(os.environ.get("POLL_INTERVAL", 300)),
            "test_namespace": os.environ.get("TEST_NAMESPACE", "flux-system"),
        }

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    config["github_token"] = config.get("github_token") or os.environ.get(
        "GITHUB_TOKEN"
    )
    config["labels"] = config.get("labels") or os.environ.get(
        "LABELS", "updatecli,traefik"
    ).split(",")
    return config


def run_tests(config):
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
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "test_results": test_results,
    }


def parse_pytest_output(output):
    results = []
    lines = output.split("\n")
    for line in lines:
        if "[CHECK]" in line:
            results.append({"description": line.split("[CHECK]")[1].strip()})
    return results


def post_comment_to_pr(github, repo, pr_number, body):
    try:
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)
        logger.info(f"Posted comment to PR #{pr_number}")
    except Exception as e:
        logger.error(f"Error posting comment: {e}")


def format_test_results(success, branch, test_results, test_output):
    status = "✅ All tests passed" if success else "❌ Tests failed"

    test_lines = []
    for test in test_results:
        icon = "✅"
        test_lines.append(f"{icon} {test['description']}")

    test_summary = "\n".join(test_lines) if test_lines else "No test results"

    body = f"""## Traefik Upgrade Test Results {status}

**Branch:** `{branch}`

**Timestamp:** {datetime.now().isoformat()}

### Test Results
{test_summary}
"""
    return body


def process_pr(pr_info, config, flux_manager, poller, dry_run=True):
    pr_number = pr_info["number"]
    branch = pr_info["head_branch"]
    sha = pr_info["head_sha"]
    html_url = pr_info["html_url"]

    logger.info(f"Processing PR #{pr_number} - Branch: {branch}")

    version_from = flux_manager.get_current_version()
    if not version_from:
        logger.error("Could not get current version")
        return

    if dry_run:
        logger.info(f"[DRY-RUN] Updating GitRepository to branch '{branch}'")
        success = flux_manager.update_gitrepository_branch(branch, dry_run=False)
        if not success:
            logger.error("Failed to update GitRepository")
            return

        logger.info("Waiting for Kustomization to reconcile...")
        kustomization_ready = flux_manager.wait_for_reconciliation(timeout_seconds=300)
        if not kustomization_ready:
            logger.warning("Kustomization reconciliation failed, retrying once...")
            kustomization_ready = flux_manager.wait_for_reconciliation(
                timeout_seconds=300
            )

        if not kustomization_ready:
            logger.error(
                "Kustomization reconciliation failed after retry, continuing anyway..."
            )

        logger.info("Waiting for HelmRelease to reconcile...")
        helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)
        if not helmrelease_ready:
            logger.warning("HelmRelease reconciliation failed, retrying once...")
            helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)

        if not helmrelease_ready:
            logger.error(
                "HelmRelease reconciliation failed after retry, continuing anyway..."
            )

        test_result = run_tests(config)

        comment_body = format_test_results(
            test_result["success"],
            branch,
            test_result["test_results"],
            test_result["output"],
        )
        logger.info(f"[DRY-RUN] Would post comment to PR #{pr_number}:\n{comment_body}")
    else:
        success = flux_manager.update_gitrepository_branch(branch, dry_run=False)
        if not success:
            logger.error("Failed to update GitRepository")
            return

        logger.info("Waiting for Kustomization to reconcile...")
        kustomization_ready = flux_manager.wait_for_reconciliation(timeout_seconds=300)
        if not kustomization_ready:
            logger.warning("Kustomization reconciliation failed, retrying once...")
            kustomization_ready = flux_manager.wait_for_reconciliation(
                timeout_seconds=300
            )

        if not kustomization_ready:
            logger.error(
                "Kustomization reconciliation failed after retry, continuing anyway..."
            )

        logger.info("Waiting for HelmRelease to reconcile...")
        helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)
        if not helmrelease_ready:
            logger.warning("HelmRelease reconciliation failed, retrying once...")
            helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)

        if not helmrelease_ready:
            logger.error(
                "HelmRelease reconciliation failed after retry, continuing anyway..."
            )

        test_result = run_tests(config)

        github = poller.github
        repo = poller.repo

        comment_body = format_test_results(
            test_result["success"],
            branch,
            test_result["test_results"],
            test_result["output"],
        )
        post_comment_to_pr(github, repo, pr_number, comment_body)

    poller.mark_pr_processed(pr_number)


def run_poll(config):
    logger.info("=" * 50)
    logger.info("Starting poll cycle...")

    poller = Poller(config)
    flux_manager = FluxManager(config)

    prs = poller.poll()

    if prs:
        for pr in prs:
            if poller.is_pr_already_processed(pr["number"]):
                logger.info(f"PR #{pr['number']} already processed, skipping")
                continue

            process_pr(
                pr, config, flux_manager, poller, dry_run=config.get("dry_run", True)
            )

    logger.info("Poll cycle complete")
    logger.info("=" * 50)

    return flux_manager


flux_manager_global = None
config_global = None


# def signal_handler(signum, frame):
#     logger.info("Received Ctrl+C, reverting GitRepository to main branch...")
#     if flux_manager_global:
#         flux_manager_global.revert_to_main()
#     sys.exit(0)


@click.command()
@click.option("--config", "-c", default=DEFAULT_CONFIG_PATH, help="Path to config file")
@click.option("--run-once", is_flag=True, help="Run once and exit")
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Dry-run mode (default: dry-run)"
)
@click.option(
    "--interval", "-i", default=300, help="Poll interval in seconds (default: 300)"
)
def main(config, run_once, dry_run, interval):
    # signal.signal(signal.SIGINT, signal_handler)

    config_data = load_config(config)
    config_data["dry_run"] = dry_run
    config_data["poll_interval"] = interval

    global flux_manager_global, config_global
    config_global = config_data

    logger.info(f"Starting Traefik Poller")
    logger.info(f"  Config: {config}")
    logger.info(f"  Dry-run: {dry_run}")
    logger.info(f"  Run-once: {run_once}")
    logger.info(f"  Interval: {interval}s")

    if run_once:
        flux_manager_global = run_poll(config_data)
    else:
        flux_manager_global = run_poll(config_data)

        schedule.every(interval).seconds.do(run_poll, config=config_data)

        logger.info(f"Scheduling polls every {interval} seconds...")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    main()
