import os
import sys
import logging
import time
import schedule
import yaml
import click
import subprocess
from datetime import datetime

from poller import Poller
from flux import FluxManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')


def load_config(config_path=None):
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}")
        return {
            'github_token': os.environ.get('GITHUB_TOKEN'),
            'repo': os.environ.get('REPO', 'sarfarazahmad19/opencode-k8s'),
            'label': os.environ.get('LABEL', 'traefik'),
            'flux_namespace': os.environ.get('FLUX_NAMESPACE', 'flux-system'),
            'gitrepo_name': os.environ.get('GITREPO_NAME', 'flux-system'),
            'poll_interval': int(os.environ.get('POLL_INTERVAL', 300)),
            'test_namespace': os.environ.get('TEST_NAMESPACE', 'flux-system'),
        }
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    config['github_token'] = config.get('github_token') or os.environ.get('GITHUB_TOKEN')
    return config


def run_tests(config):
    logger.info("Running pytest tests...")
    
    test_dir = os.path.join(os.path.dirname(__file__), '..', 'tests')
    if not os.path.exists(test_dir):
        logger.error(f"Tests directory not found: {test_dir}")
        return False
    
    namespace = config.get('test_namespace', 'flux-system')
    
    result = subprocess.run(
        ['pytest', '-v', '--tb=short', f'--namespace={namespace}', test_dir],
        capture_output=True,
        text=True
    )
    
    logger.info(f"Pytest output:\n{result.stdout}")
    if result.stderr:
        logger.warning(f"Pytest stderr:\n{result.stderr}")
    
    return result.returncode == 0


def post_comment_to_pr(github, repo, pr_number, body):
    try:
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)
        logger.info(f"Posted comment to PR #{pr_number}")
    except Exception as e:
        logger.error(f"Error posting comment: {e}")


def format_test_results(success, version_from, version_to, test_output):
    status = "✅ All tests passed" if success else "❌ Tests failed"
    
    body = f"""## Traefik Upgrade Test Results {status}

**Version:** {version_from} → {version_to}

**Timestamp:** {datetime.now().isoformat()}

```
{test_output}
```

**Status:** {'All tests passed' if success else 'Tests failed'}
"""
    return body


def process_pr(pr_info, config, flux_manager, poller, dry_run=True):
    pr_number = pr_info['number']
    branch = pr_info['head_branch']
    sha = pr_info['head_sha']
    html_url = pr_info['html_url']
    
    logger.info(f"Processing PR #{pr_number} - Branch: {branch}")
    
    version_from = flux_manager.get_current_version()
    if not version_from:
        logger.error("Could not get current version")
        return
    
    if dry_run:
        logger.info(f"[DRY-RUN] Would update GitRepository to branch '{branch}'")
        logger.info(f"[DRY-RUN] Would run tests")
        logger.info(f"[DRY-RUN] Would post comment to PR #{pr_number}")
        
        test_success = True
        test_output = "[DRY-RUN] Test execution skipped"
    else:
        success = flux_manager.update_gitrepository_branch(branch, dry_run=False)
        if not success:
            logger.error("Failed to update GitRepository")
            return
        
        logger.info("Waiting for Flux to reconcile...")
        flux_manager.wait_for_reconciliation(timeout_seconds=300)
        
        version_to = flux_manager.get_current_version()
        
        test_success = run_tests(config)
        
        test_output = f"Version after upgrade: {version_to}"
        
        github = poller.github
        repo = poller.repo
        
        comment_body = format_test_results(test_success, version_from, version_to, test_output)
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
            if poller.is_pr_already_processed(pr['number']):
                logger.info(f"PR #{pr['number']} already processed, skipping")
                continue
            
            process_pr(pr, config, flux_manager, poller, dry_run=config.get('dry_run', True))
    
    logger.info("Poll cycle complete")
    logger.info("=" * 50)


@click.command()
@click.option('--config', '-c', default=DEFAULT_CONFIG_PATH, help='Path to config file')
@click.option('--run-once', is_flag=True, help='Run once and exit')
@click.option('--dry-run/--no-dry-run', default=True, help='Dry-run mode (default: dry-run)')
@click.option('--interval', '-i', default=300, help='Poll interval in seconds (default: 300)')
def main(config, run_once, dry_run, interval):
    config_data = load_config(config)
    config_data['dry_run'] = dry_run
    config_data['poll_interval'] = interval
    
    logger.info(f"Starting Traefik Poller")
    logger.info(f"  Config: {config}")
    logger.info(f"  Dry-run: {dry_run}")
    logger.info(f"  Run-once: {run_once}")
    logger.info(f"  Interval: {interval}s")
    
    if run_once:
        run_poll(config_data)
    else:
        run_poll(config_data)
        
        schedule.every(interval).seconds.do(run_poll, config=config_data)
        
        logger.info(f"Scheduling polls every {interval} seconds...")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == '__main__':
    main()
