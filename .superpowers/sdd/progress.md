# SDD Progress Ledger — attack-algorithm (P2)

Plan: `docs/superpowers/plans/2026-08-13-attack-algorithm.md`
Branch: `feat/attack-algorithm` (created in Task 1)

- [x] Task 1: complete (commits deef2d6..5a8a675, review clean; fixed brief-inherited __main__ path off-by-one; accepted vendored pyproject.toml for aicomp CLI)
- [x] Task 2: clean-token generator (commit 7378d7e, review clean; 4 new tests, full suite 5/5)
- [x] Task 3: constraint validator (commit 68ef71c, review clean; 6 new tests, full suite 11/11)
- [x] Task 4: family A (commit 0ded574, review clean; 4 new tests, full suite 15/15)
- [x] Task 5: family B (commit 7b0680b, review clean; 2 new tests, full suite 17/17)
- [ ] Task 6: family C (confused-deputy)
- [ ] Task 7: family D (mixed)
- [ ] Task 8: Phase 2 search
- [ ] Task 9: Phase 1 + finalize
- [ ] Task 10: smoke validation

## Minor findings (triage at final whole-branch review)

- Task 2: `task-2-report.md` change inventory omitted commit 5a8a675 / plan-doc fixtures fix — report accuracy only; controller note appended to report.
- Task 2: `_product` import mid-file (brief-mandated verbatim; PEP 8 placement only, no behavior).
- Task 2: `is_clean` case-insensitivity and `clean_urls/clean_recipients` limit-truncation untested (brief-specified test set; optional coverage).
- Task 3: `("",)` empty-string message case unpinned by any test (valid per contract; policy question for later filtering tasks — implementer flagged it too).
- Task 4 (implementer concern, resolve at Task 9 wiring): `clean_urls` pool caps at 132 distinct domains (22 words × 6 TLDs) but family-A density defaults need 600 URL-slots — underfills the candidate set and caps cell diversity. Fix at Task 9: expand `_CLEAN_WORDS`/`_CLEAN_TLDS` to ≥600 distinct clean domains (all pre-screened with `is_clean`) or rescale densities to the pool.
- Task 4 (reviewer Minor, brief-mandated): `made += 1` outside `_valid_candidate` guard; `zip(densities, per_density)` silent truncation; test URL-count assertion via substring (prefix-collision risk); report line-count numerics.
- Task 5 (reviewer Minor, brief-mandated): mid-file `family_b_candidates` import; `_WASH_FILES` duplicated between impl and test (intentional pinning); report line-count numerics.
