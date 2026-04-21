# Team Workflow Upgrade — Post-MVP Plan

**Status:** Deferred. Current workflow = ad-hoc direct-to-main with good commit messages, fast-prototype mode for MVP. Revisit this doc when onboarding teammates or after the MVP ships.

**Why deferred:** Solo dev + Claude, racing to MVP. PR/CI ceremony adds overhead without proportional benefit at this stage. Capture the industry-standard team workflow here so it's ready to activate when the team grows.

---

## Industry consensus for high-velocity teams

The pattern every modern team converges on is **GitHub Flow with small PRs + trunk-based discipline**:

1. **Main is always deployable.** No `develop` / `release` branches. Everything merges to main.
2. **Feature branches are short-lived.** Born → merged within **1–3 days**. A branch that lives a week is a smell.
3. **PRs are small.** Target: **< 400 lines, reviewable in 15 minutes**. Bigger than that, split it.
4. **One reviewer approval is enough.** Two-reviewer requirements slow teams down without catching proportionally more bugs.
5. **CI runs on every PR.** Tests + linter + type-check gate the merge button. No "I'll verify locally."
6. **Feature flags for incomplete work.** Half-finished features merge to main behind a flag rather than sitting on a branch for weeks.
7. **Squash merges** as default. Each PR = one commit on main. Clean history, easy `git bisect`.
8. **Branch protection on main.** Require PR + ≥1 approval + passing CI. Prevents accidental direct pushes.

This is literally how Shopify, Stripe, GitHub, and most YC-stage startups ship.

---

## Concrete activation checklist (when ready)

### Immediate (before first teammate joins)

1. **Enable branch protection on `main`** via GitHub → Settings → Branches:
   - [ ] Require pull request before merging
   - [ ] Require 1 approval
   - [ ] Dismiss stale approvals on new commits
   - [ ] Require status checks to pass (add them in step 2)
   - [ ] (Optional) Require conversation resolution before merging

2. **Add CI** — `.github/workflows/ci.yml` that runs on every PR:
   - [ ] `pytest backend/tests/ -k "not integration"` (unit tests, ~2s)
   - [ ] `cd frontend && npm run build` (TypeScript check + bundle)
   - [ ] Optional: Ruff / Black for Python formatting
   - [ ] Optional: ESLint for frontend
   - [ ] Mark these as "required" in branch protection

3. **Set merge strategy** in GitHub repo settings:
   - [ ] **Allow squash merge** ← default
   - [ ] Disable merge commits (unless you want commit granularity)
   - [ ] Disable rebase merge (harder to reason about)

4. **Add a PR template** at `.github/pull_request_template.md` with sections: Summary, Why, Test plan.

5. **Enable GitHub merge queue** (Settings → Branches → merge queue) — serializes merges, re-runs CI on each. Prevents the stack-merge mess we hit during the storage refactor.

### PR sizing rules (share with team as norms)

| Type | Target size | Turnaround |
|---|---|---|
| Bug fix | < 50 lines | < 4 hours |
| Feature increment | 100–300 lines | same day merge |
| Refactor | < 400 lines, isolate renames in their own PR | 1 day |
| Schema / data migration | Any size, but ALWAYS its own PR with explicit reviewer | 1 day |

**Anything bigger should be broken up.** If you can't split it, write a design doc (see `docs/superpowers/specs/`) and split the implementation into multiple PRs against the same doc.

### The "done in a day" principle

If a branch takes more than 3 days to finish:
- Merge what you have behind a feature flag
- Let teammates review incrementally
- Avoid the giant-PR-at-the-end problem we had with the storage refactor

### Team norms (culture)

- **Everyone reviews** — no dedicated "senior approver" bottleneck. Anyone on the team can approve.
- **PR descriptions include context** — what, why, how to test. The commit messages alone aren't enough for someone without your head-state.
- **Convention: "ship small, ship often"** — a PR that's been open for 2 days has stale context. Merge or close it.
- **Tests in the same PR as the feature** — no "tests coming in a follow-up."

### Tools worth adopting for MVP-pace teams

| Tool | What it does | Why it matters |
|---|---|---|
| **GitHub merge queue** | Serializes merges, re-runs CI on each | Prevents the stack-merge issues we hit during the storage refactor |
| **Dependabot / Renovate** | Auto-PRs for dep updates | Keeps security patches flowing |
| **Preview deploys** (Vercel/Netlify for frontend, Fly.io for backend) | Each PR gets a live URL | Reviewers test UX, not just code |
| **Linear / GitHub Projects** | Ties PRs to tickets | Traceability from "why" to "what" |
| **PR templates** (`.github/pull_request_template.md`) | Standardizes PR descriptions | Makes review faster |

---

## Retro notes from the 2026-04-20 storage refactor

What went wrong on that push that this workflow would have prevented:

1. **4 PRs stacked with feature-branch bases** → merges cascaded into each other instead of into main. Fixed via catchup PR #8. Merge queue would have prevented this entirely.
2. **PR #6 was 1,200 lines across 30 files** → in a team context, nobody could have reviewed that in 15 minutes. Should have been split into ~6 small PRs.
3. **Local-first for ~4 hours before pushing** → teammates couldn't see progress or catch drift early. "Daily push" would have surfaced the stacked-merge issue earlier.
4. **No CI** → all verification was manual. Tests passing locally isn't the same as tests passing on a fresh clone with just the PR's changes.

None of these were fatal — we verified, fixed, and shipped. But at team scale the blast radius of each would be bigger.

---

## The one-sentence answer (for when we activate this)

**GitHub Flow + branch protection + CI + squash merges + PRs under 400 lines merged within a day + feature flags for incomplete work.**

---

## Current mode (2026-04-20 → TBD)

- Solo dev + Claude
- Direct commits to main with good Conventional Commit messages
- No PR ceremony, no CI, no branch protection
- Local iterate → push when done
- Goal: MVP ready ASAP, worry about process later

Revisit this doc when: (a) first teammate joins, OR (b) MVP has shipped and we're entering a maintenance phase, OR (c) the product graduates out of prototype.
