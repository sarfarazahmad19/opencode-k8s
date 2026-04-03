import os
import logging
from datetime import datetime
from github import Github

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, config):
        self.config = config
        self.github = Github(config.get('github_token'))
        self.repo = self.github.get_repo(config.get('repo'))
        self.label = config.get('label', 'traefik')
        self.processed_prs = set()

    def get_prs_with_label(self):
        prs = []
        try:
            issues = self.repo.get_issues(state='open', labels=[self.label])
            for issue in issues:
                if issue.pull_request:
                    pr = issue.as_pull_request()
                    prs.append({
                        'number': pr.number,
                        'title': pr.title,
                        'head_branch': pr.head.ref,
                        'head_sha': pr.head.sha,
                        'html_url': pr.html_url,
                    })
        except Exception as e:
            logger.error(f"Error fetching PRs: {e}")
        return prs

    def is_pr_already_processed(self, pr_number):
        return pr_number in self.processed_prs

    def mark_pr_processed(self, pr_number):
        self.processed_prs.add(pr_number)

    def poll(self):
        logger.info(f"Polling for PRs with label '{self.label}'...")
        prs = self.get_prs_with_label()
        
        if not prs:
            logger.info("No PRs found with label 'traefik'")
            return None

        for pr in prs:
            logger.info(f"Found PR #{pr['number']}: {pr['title']}")
            logger.info(f"  Branch: {pr['head_branch']}, SHA: {pr['head_sha']}")

        return prs
