---
name: create-pull-request
description: Draft and open a GitHub pull request for the current branch, using this repo's .github/pull_request_template.md to structure the description. Use whenever the user asks to create/open a PR, wants to submit the current branch for review, or says things like "PRを作って", "プルリクを作成して", "レビュー依頼したい".
---

# Create Pull Request

## When to use

The user wants the current branch's work opened as a GitHub pull request against
`main` — whether asked directly ("open a PR", "PRを作って", "プルリクを作成して") or
implied ("this is ready for review").

## Steps

1. **Check working tree state** — run `git status`. If there are uncommitted changes
   the user wants included, stage and commit them first, following standard git-safety
   rules (show the diff, confirm the commit message with the user, never `git add -A`
   blindly).

2. **Gather the full set of changes, not just the latest commit** — run
   `git log main..HEAD --oneline` and `git diff main...HEAD` to see everything that
   will land in the PR, across all commits on the branch.

3. **Load the PR template** — read `.github/pull_request_template.md`. If it doesn't
   exist, fall back to a minimal Summary / Changes / Test plan / Notes structure, and
   ask the user if they'd like a template file created for future PRs.

4. **Draft the PR title and body**
   - Title: short (under ~70 chars), imperative mood, matching this repo's commit
     style (`feat:`, `fix:`, `docs:`, …).
   - Body: fill in every section of the template from the actual diff/log — no
     placeholders left unfilled.
     - **Summary**: why this change exists.
     - **Changes**: bullet list of what changed.
     - **Test plan**: a checklist of what was actually verified — be honest about
       what's untested rather than claiming coverage that doesn't exist.
     - **Notes**: anything else the reviewer should know (related issues, follow-ups,
       known limitations).

5. **Check for an existing open PR on this branch** — `gh pr list --head <branch>` —
   to avoid creating a duplicate. If one exists, surface it instead of proceeding.

6. **Confirm with the user** before creating anything visible on GitHub. Show the
   drafted title + body and get explicit go-ahead — this is an external-visibility
   action, so don't skip this even if earlier steps in the conversation were
   pre-approved.

7. **Push the branch** if it isn't already pushed / up to date:
   `git push -u origin <branch>`.

8. **Create the PR**, using a heredoc so multi-line Markdown survives intact:
   ```bash
   gh pr create --base main --head <branch> --title "<title>" --body "$(cat <<'EOF'
   <body>
   EOF
   )"
   ```

9. **If `gh` isn't installed or not authenticated** (`gh auth status` fails), tell the
   user directly rather than working around it (e.g. don't hunt for tokens or hit the
   GitHub API by hand). Ask the user to install/authenticate themselves — suggest
   `! gh auth login` so the output lands in the session — then retry from step 7/8.

10. **Report the PR URL** back to the user as the final output.

## Notes

- Never run `gh pr create` (or any push) without explicit go-ahead in that turn — a
  prior approval for a different PR doesn't carry over.
- Base branch for this repo is `main`; double-check this hasn't changed if it's been a
  while since last use.
