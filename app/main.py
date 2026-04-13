import os
import sys
import logging
import time
import schedule
import yaml
import argparse
import subprocess
import signal
import tempfile
import shutil
from datetime import datetime

from poller import Poller
from flux import FluxManager
from goal_writer import write_goal
from runner import run_before_tests, run_after_tests, post_results_to_pr

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


def process_pr(pr_info, config, flux_manager, poller, dry_run=False):
    pr_number = pr_info["number"]
    branch = pr_info["head_branch"]
    sha = pr_info["head_sha"]
    html_url = pr_info["html_url"]

    logger.info(f"Processing PR #{pr_number} - Branch: {branch}")

    version_from, gen_from = flux_manager.get_current_version_with_generation()
    if not version_from:
        logger.error("Could not get current version")
        return

    logger.info("Running before tests to verify current state...")
    before_result = run_before_tests(config)
    if not before_result["success"]:
        logger.warning("Before tests failed, continuing anyway...")

    if not dry_run and config.get("github_token"):
        post_results_to_pr(html_url, before_result, version=version_from)

    if dry_run:
        logger.info(f"[DRY-RUN] Updating GitRepository to branch '{branch}'")

    success = flux_manager.update_gitrepository_branch(branch, dry_run=False)
    if not success:
        logger.error("Failed to update GitRepository")
        return

    flux_manager.force_gitrepository_reconcile()

    logger.info("Waiting for Kustomization to reconcile...")
    kustomization_ready = flux_manager.wait_for_reconciliation(timeout_seconds=300)
    if not kustomization_ready:
        logger.warning("Kustomization reconciliation failed, retrying once...")
        kustomization_ready = flux_manager.wait_for_reconciliation(timeout_seconds=300)

    if not kustomization_ready:
        logger.error(
            "Kustomization reconciliation failed after retry, continuing anyway..."
        )

    flux_manager.force_kustomization_reconcile()

    logger.info("Waiting for HelmRelease to reconcile...")
    helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)
    if not helmrelease_ready:
        logger.warning("HelmRelease reconciliation failed, retrying once...")
        helmrelease_ready = flux_manager.wait_for_helmrelease_ready(dry_run=False)

    if not helmrelease_ready:
        logger.error(
            "HelmRelease reconciliation failed after retry, continuing anyway..."
        )

    flux_manager.force_helmrelease_reconciliation()

    logger.info("Waiting for generation to increment...")
    generation_incremented = flux_manager.wait_for_generation_increment(gen_from)
    if not generation_incremented:
        logger.error("Generation did not increment - version unchanged")
        post_results_to_pr(
            html_url, None, version=f"FAILED - version unchanged ({version_from})"
        )
        return

    target_version = flux_manager.get_current_version()
    k8s_context = subprocess.check_output(
        ["kubectl", "config", "current-context"], text=True
    ).strip()
    repo_url = f"git@github.com:{config.get('repo')}.git"

    goal_tempdir = (
        tempfile.mkdtemp(prefix="opencode_goal_")
        if not config.get("no_opencode_run")
        else "/tmp"
    )
    goal_path = write_goal(
        tempdir=goal_tempdir,
        software_name="traefik",
        current_version=version_from or "unknown",
        pr_branch=branch,
        pr_url=html_url,
        target_version=target_version or "unknown",
        helmrelease_namespace=config.get("helmrelease_namespace", "traefik"),
        helmrelease_name="traefik",
        flux_namespace=config.get("flux_namespace", "flux-system"),
        gitrepo_name=config.get("gitrepo_name", "flux-system"),
        repo_path=config.get("repo_path"),
        repo_url=repo_url,
        ssh_key_path=config.get("ssh_key_path"),
        k8s_context=k8s_context,
        dry_run="true" if dry_run else "false",
    )

    if config.get("no_opencode_run"):
        logger.info("=== GOAL.md ===")
        with open(goal_path, "r") as f:
            print(f.read())
        logger.info("=== END GOAL.md ===")
        poller.mark_pr_processed(pr_number)
        return

    logger.info("Running opencode run...")
    tempdir = tempfile.mkdtemp(prefix="opencode_")
    try:
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = config.get("github_token") or os.environ.get(
            "GITHUB_TOKEN", ""
        )
        env["REPO"] = config.get("repo", "sarfarazahmad19/opencode-k8s")
        result = subprocess.run(
            [
                "opencode",
                "run",
                "--dangerously-skip-permissions",
                "true",
                "-m",
                "opencode/big-pickle",
                f"Work per the instructions in {goal_path}",
            ],
            cwd=tempdir,
            env=env,
            timeout=600,
        )
        logger.info(f"opencode run finished with exit code {result.returncode}")
    finally:
        shutil.rmtree(tempdir)

    logger.info("Reverting GitRepository to main branch...")
    flux_manager.update_gitrepository_branch("main", dry_run=False)
    flux_manager.force_gitrepository_reconcile()

    logger.info("Waiting for Kustomization to reconcile...")
    flux_manager.wait_for_reconciliation(timeout_seconds=300)

    logger.info("Reverting HelmRelease to main branch...")
    flux_manager.force_helmrelease_reconciliation()

    logger.info("Waiting for HelmRelease to reconcile...")
    flux_manager.wait_for_helmrelease_ready(dry_run=False, timeout_seconds=300)

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
                pr, config, flux_manager, poller, dry_run=config.get("dry_run", False)
            )

    logger.info("Poll cycle complete")
    logger.info("=" * 50)

    return flux_manager


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Traefik Upgrade Poller")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--no-opencode-run", action="store_true", default=False)
    args = parser.parse_args()

    config_data = load_config(args.config)
    config_data["dry_run"] = args.dry_run
    config_data["no_opencode_run"] = args.no_opencode_run

    logger.info(f"Starting Traefik Poller")
    logger.info(f"  Config: {args.config}")
    logger.info(f"  Dry-run: {args.dry_run}")
    logger.info(f"  No opencode run: {args.no_opencode_run}")
    logger.info(f"  Run-once: {args.run_once}")
    logger.info(f"  Interval: {args.interval}s")

    flux_manager_global = run_poll(config_data)

    if not args.run_once:
        schedule.every(args.interval).seconds.do(run_poll, config=config_data)
        logger.info(f"Scheduling polls every {args.interval} seconds...")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    main()
