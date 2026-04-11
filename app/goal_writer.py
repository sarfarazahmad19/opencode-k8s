import os


def write_goal(
    tempdir: str,
    pr_branch: str,
    target_version: str,
    helmrelease_namespace: str,
    helmrelease_name: str,
    flux_namespace: str,
    gitrepo_name: str,
    repo_path: str,
    ssh_key_path: str,
) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "GOAL.md.template")

    with open(template_path, "r") as f:
        template = f.read()

    content = template.format(
        pr_branch=pr_branch,
        target_version=target_version,
        helmrelease_name=helmrelease_name,
        helmrelease_namespace=helmrelease_namespace,
        gitrepo_name=gitrepo_name,
        flux_namespace=flux_namespace,
        repo_path=repo_path,
        ssh_key_path=ssh_key_path,
    )

    goal_path = os.path.join(tempdir, "GOAL.md")
    with open(goal_path, "w") as f:
        f.write(content)

    return goal_path
