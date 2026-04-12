# TODO: Refactor Python App → GOAL.md Generator + Request Router

## Problem
`main.py` does too much: polls PRs, updates GitRepository, generates GOAL.md, runs opencode, runs tests, posts results to PR.

## Goal
Split into:
1. **GOAL.md Generator** - Takes PR/version info → outputs GOAL.md
2. **Request Router** - Routes requests to pluggable handlers

## Proposed Structure

```
app/
├── main.py              # Entry: CLI + routing only
├── config.yaml          # Plugin configuration
├── plugins/             # Pluggable components
│   ├── pr_poller.py     # Detect PRs (polling or webhook)
│   ├── test_runner.py   # Run pytest (from runner.py)
│   ├── github_poster.py # Post results to PR
│   └── flux_ops.py      # GitRepository updates
├── templates/
│   └── GOAL.md.template
└── goal_generator.py    # Generate GOAL.md from inputs
```

## Benefits
- Testable - each plugin unit tested
- Reusable - generator standalone  
- Swappable - polling ↔ webhook
- Clean - main.py just routes