import os
import logging
from datetime import datetime
from github import Github

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, config):
        self.config = config
        self.github = Github(config.get("github_token"))
        self.repo = self.github.get_repo(config.get("repo"))
        self.labels = config.get("labels", [config.get("label", "traefik")])
        self.label = config.get("label", "traefik")
        self.processed_prs = set()

    def get_prs_with_labels(self, required_labels):
        prs = []
        try:
            issues = self.repo.get_issues(state="open")
            for issue in issues:
                if issue.pull_request:
                    pr = issue.as_pull_request()
                    pr_labels = {l.name for l in pr.labels}
                    if all(label in pr_labels for label in required_labels):
                        prs.append(
                            {
                                "number": pr.number,
                                "title": pr.title,
                                "head_branch": pr.head.ref,
                                "head_sha": pr.head.sha,
                                "html_url": pr.html_url,
                            }
                        )
        except Exception as e:
            logger.error(f"Error fetching PRs: {e}")
        return prs

    def get_prs_with_label(self):
        prs = []
        try:
            issues = self.repo.get_issues(state="open", labels=[self.label])
            for issue in issues:
                if issue.pull_request:
                    pr = issue.as_pull_request()
                    prs.append(
                        {
                            "number": pr.number,
                            "title": pr.title,
                            "head_branch": pr.head.ref,
                            "head_sha": pr.head.sha,
                            "html_url": pr.html_url,
                        }
                    )
        except Exception as e:
            logger.error(f"Error fetching PRs: {e}")
        return prs

    def is_pr_already_processed(self, pr_number):
        return pr_number in self.processed_prs

    def mark_pr_processed(self, pr_number):
        self.processed_prs.add(pr_number)

    def poll(self):
        logger.info(f"Polling for PRs with labels {self.labels}...")
        prs = self.get_prs_with_labels(self.labels)

        if not prs:
            logger.info(f"No PRs found with labels {self.labels}")
            return None

        for pr in prs:
            logger.info(f"Found PR #{pr['number']}: {pr['title']}")
            logger.info(f"  Branch: {pr['head_branch']}, SHA: {pr['head_sha']}")

        return prs
