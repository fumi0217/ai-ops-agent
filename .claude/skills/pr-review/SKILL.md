---
name: pr-review
description: Full pull-request review in one pass — whether the diff matches its stated intent (commit messages, PR title/body, and this repo's docs — README/CLAUDE.md/docs/adr), whether the diff itself has correctness bugs or obvious code-quality issues, and whether the PR's Test plan reflects real, adequate verification for the change. Posts a single OK/NG verdict with findings as a PR comment. Use when the user asks to review a PR, wants an automated pre-merge check, or says things like "PRレビューして", "意図とズレてないか確認して". Requires a PR to already exist for the branch (see create-pull-request skill). This covers the full PR-review job (intent + correctness + test sufficiency), not just code quality — for a deeper, effort-tunable code-only review with inline comments or auto-fix, use the code-review skill instead.
---

# PR Review

## When to use

The user wants an already-open pull request reviewed the way a human reviewer would
before approving a merge — not just "is the code well-written" but the full PR-review
job: does the diff do what it claims, does it hold up on its own merits, and was it
actually verified adequately? This skill checks all three in a single pass and posts
one summary verdict as a PR comment. It does not create the PR, and it does not
replace a deeper code-only review pass (`code-review`) when the diff is large or
high-risk.

## Steps

1. **Identify the PR for the current branch.**
   ```bash
   gh pr view --json number,title,body,baseRefName,headRefName,url
   ```
   If no PR exists for this branch, tell the user and stop — suggest running the
   `create-pull-request` skill first. Do not create a PR as part of this skill.

2. **Gather the stated intent.**
   - The PR title and body (from step 1), including its Test plan section.
   - The branch's commit messages: `git log <base>..HEAD --oneline` and
     `git log <base>..HEAD` (full messages) — commit messages often state intent more
     precisely than the PR body.

3. **Gather the actual change.**
   ```bash
   git diff <base>...HEAD
   git diff <base>...HEAD --stat
   ```

4. **Gather relevant repo context** to judge consistency against — read whichever of
   these exist and are relevant to the files touched by the diff:
   - `README.md`
   - `CLAUDE.md`
   - `docs/adr/*.md`
   - Any other doc the diff itself touches or claims to update.

5. **Check the diff against its stated intent.**
   - Does the diff actually do what the commit messages / PR description say it does?
     (e.g. a commit claiming "remove unused X" but leaving a reference to X somewhere,
     a PR body describing a change that isn't in the diff, or a diff that does more
     than the description mentions).
   - Does anything contradict this repo's documented conventions or decisions
     (CLAUDE.md's rules, an ADR's stated decision) without explanation?
   - Anything that shouldn't be in a public portfolio repo: credentials, API keys,
     `.env` (not `.env.example`), debug/leftover code, accidentally-committed files.

6. **Check whether the change was adequately verified.**
   - Does the PR body's Test plan section describe verification that's actually
     appropriate for what this diff touches? (e.g. a change to `mcp_server`'s tool
     logic claiming only "read the code" with no execution is thin; a docs-only
     change needing no runtime verification is fine as-is.)
   - Is the Test plan checklist actually checked off, or left as unfilled
     placeholders from the template?
   - Does the diff itself show evidence consistent with the claimed verification
     (e.g. if the PR claims a bug was reproduced and fixed, does the diff plausibly
     fix that failure mode)?
   - This repo has no automated test suite (see CLAUDE.md) — "adequate verification"
     here means real manual verification (running the affected service, exercising
     the changed path) proportionate to the change's risk, not unit test coverage.
   - Don't demand verification that doesn't make sense for the change (e.g. don't
     flag a pure documentation/ADR change for lacking a browser test).

7. **Review the diff itself for correctness and quality**, with the same rigor as a
   careful human code review — read the actual changed code, not just the summary:
   - **Correctness**: logic errors, off-by-one/edge cases, unhandled error paths,
     race conditions, incorrect assumptions about inputs or state.
   - **Quality**: dead code, unnecessary duplication, obvious simplification
     opportunities, misleading names/comments/docstrings.
   - Only report findings you can point to concretely (file + line, and the specific
     failure scenario) — don't pad the report with vague stylistic opinions.
   - This is one pass at normal depth, not an exhaustive multi-round audit. For a
     large or high-risk diff, tell the user this skill's coverage is lighter than
     `code-review`'s higher effort levels and suggest running that instead/in addition.

8. **Form a verdict: OK or NG.**
   - OK: the diff matches its stated intent, verification is adequate for the change,
     and no correctness/quality findings from step 7 survive scrutiny.
   - NG: the diff doesn't match its stated intent, a red flag was found in step 5,
     verification is missing/inadequate for the change's risk (step 6), or a concrete
     correctness/quality issue was found in step 7 — list each finding with file
     references.

9. **Draft the PR comment** using this shape:
   ```markdown
   ## 🤖 PR Review: OK|NG

   **確認した意図**: <PR title/body・コミットメッセージの要約>

   **diffとの整合性**: <一致している/していない、根拠>

   **検証の十分性**: <Test planの内容が変更内容に見合っているか>

   **コード品質・バグ**: <箇条書き、file:line付き。なければ「特になし」>

   **懸念点**: <セキュリティ/規約との矛盾など。なければ「特になし」>
   ```

10. **Confirm with the user before posting** — show the drafted verdict/comment and
    get explicit go-ahead. Posting to a PR is externally visible; do not skip this
    even if the user asked for the whole flow up front.

11. **Post the comment.**
    ```bash
    gh pr comment <number> --body "$(cat <<'EOF'
    <comment>
    EOF
    )"
    ```

12. **Report the PR comment URL back to the user.**

## Notes

- This skill never claims verification (tests run, manual checks done) that wasn't
  actually performed — if something couldn't be checked, say so rather than silently
  marking OK.
- Complements, not replaces, the general-purpose `code-review` skill. `code-review`
  is a code-only tool (correctness/simplification), with tunable effort levels,
  inline PR comments, auto-fix, and a cloud multi-agent `ultra` mode for deeper
  coverage. `pr-review` is the broader, PR-level check a human reviewer would do
  before approving a merge — intent match, verification sufficiency, and a
  normal-depth code pass — in one fixed-depth summary comment.
