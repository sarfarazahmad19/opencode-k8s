# Changelog

## [1.1-dev-0]

### Changed

- **CLI**: Replaced `click` with `argparse` for command-line argument parsing
- **Default behavior**: `dry_run` default changed from `True` to `False` - app now commits/pushes changes by default instead of just logging them
- **Tests**: Consolidated `test_helmrelease.py` and `test_traefik_ingress.py` into single `tests/test_traefik.py` to fix pytest-dependency cross-module issues

### Added

- `--dangerously-skip-permissions true` flag to opencode run command
- `dry_run` parameter passed to `write_goal()` for GOAL.md template
- Step 0 in `GOAL.md.template` to verify HelmRelease revision matches latest git commit before running tests
- Updated force reconcile commands in GOAL.md to use `kubectl annotate` instead of `kubectl patch`

### Removed

- Duplicate code branches in `process_pr()` - unified dry_run logic
- Unused global variables (`flux_manager_global`, `config_global`)
- Commented-out signal handler code

### Functionality Preserved

- All CLI arguments work the same: `--config`, `--run-once`, `--dry-run`, `--interval`
- Polling and PR processing logic unchanged
- Fixtures and test options remain functional