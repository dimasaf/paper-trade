# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Repository

- Remote: `https://github.com/dimasaf/paper-trade.git`
- GitHub CLI is installed and authenticated for repository operations.
- GitHub Issues and native issue dependencies are enabled.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.**

If this is changed to `yes`, PRs run through the same labels and states as issues using the `gh pr` equivalents. Only external requests from `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` should enter triage; exclude `OWNER`, `MEMBER`, and `COLLABORATOR`.

GitHub shares one number space across issues and PRs. Resolve an ambiguous `#42` with `gh pr view 42`, falling back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The map is a single issue with child issues as tickets.

- **Map**: an issue labelled `wayfinder:map`, holding Notes, Decisions-so-far, and Fog.
- **Child ticket**: link it to the map as a GitHub sub-issue. If sub-issues are unavailable, put it in the map's task list and add `Part of #<map>` to the child. Use `wayfinder:<type>` labels.
- **Blocking**: use GitHub's native issue dependencies. If unavailable, add `Blocked by: #<n>, #<n>` to the issue body.
- **Frontier**: select the first open, unassigned child with no open blocker.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: comment with the answer, close the issue, and append a context pointer to the map's Decisions-so-far.
