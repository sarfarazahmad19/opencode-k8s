import os


def write_goal(
    tempdir: str,
    software_name: str,
    current_version: str,
    pr_branch: str,
    pr_url: str,
    target_version: str,
    helmrelease_namespace: str,
    helmrelease_name: str,
    flux_namespace: str,
    gitrepo_name: str,
    repo_path: str,
    repo_url: str,
    ssh_key_path: str,
    k8s_context: str,
    dry_run: str = "false",
) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "GOAL.md.template")

    with open(template_path, "r") as f:
        template = f.read()

    content = template.format(
        software_name=software_name,
        current_version=current_version,
        pr_branch=pr_branch,
        pr_url=pr_url,
        target_version=target_version,
        helmrelease_name=helmrelease_name,
        helmrelease_namespace=helmrelease_namespace,
        gitrepo_name=gitrepo_name,
        flux_namespace=flux_namespace,
        repo_path=repo_path,
        repo_url=repo_url,
        ssh_key_path=ssh_key_path,
        k8s_context=k8s_context,
        dry_run=dry_run,
    )

    goal_path = os.path.join(tempdir, "GOAL.md")
    with open(goal_path, "w") as f:
        f.write(content)

    return goal_path
