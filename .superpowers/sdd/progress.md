# SDD Progress Ledger — attack-algorithm (P2)

Plan: `docs/superpowers/plans/2026-08-13-attack-algorithm.md`
Branch: `feat/attack-algorithm` (created in Task 1)

- [x] Task 1: complete (commits deef2d6..5a8a675, review clean; fixed brief-inherited __main__ path off-by-one; accepted vendored pyproject.toml for aicomp CLI)
- [x] Task 2: clean-token generator (commit 7378d7e, review clean; 4 new tests, full suite 5/5)
- [x] Task 3: constraint validator (commit 68ef71c, review clean; 6 new tests, full suite 11/11)
- [x] Task 4: family A (commit 0ded574, review clean; 4 new tests, full suite 15/15)
- [x] Task 5: family B (commit 7b0680b, review clean; 2 new tests, full suite 17/17)
- [x] Task 6: family C (commit 07dc12c, review clean; 2 new tests, full suite 19/19)
- [x] Task 7: family D (commit 4e92030, review clean; 2 new tests, full suite 21/21)
- [x] Task 8: Phase 2 search (commits a280f66..35e294d, review clean after fix; Important #1 hops resolved by always passing 8 per plan Global Constraints + CLAUDE.md; 3 new tests, full suite 24/24)
- [x] Task 9: Phase 1 + finalize (commit 7808f52, review clean; wordlist pool expanded 132→864 clean domains (reviewer verified 864/864), _N_URLS=600, 380 candidates, 5 new tests, full suite 29/29)
- [x] Task 10: smoke validation (commit b276bd8, review clean; deterministic smoke score 0.0/0/0 as expected, pipeline end-to-end clean, validate passes, docstring note recorded)

## Minor findings (triage at final whole-branch review)

- Task 2: `task-2-report.md` change inventory omitted commit 5a8a675 / plan-doc fixtures fix — report accuracy only; controller note appended to report.
- Task 2: `_product` import mid-file (brief-mandated verbatim; PEP 8 placement only, no behavior).
- Task 2: `is_clean` case-insensitivity and `clean_urls/clean_recipients` limit-truncation untested (brief-specified test set; optional coverage).
- Task 3: `("",)` empty-string message case unpinned by any test (valid per contract; policy question for later filtering tasks — implementer flagged it too).
- Task 4 (implementer concern, resolve at Task 9 wiring): `clean_urls` pool caps at 132 distinct domains (22 words × 6 TLDs) but family-A density defaults need 600 URL-slots — underfills the candidate set and caps cell diversity. Fix at Task 9: expand `_CLEAN_WORDS`/`_CLEAN_TLDS` to ≥600 distinct clean domains (all pre-screened with `is_clean`) or rescale densities to the pool.
- Task 4 (reviewer Minor, brief-mandated): `made += 1` outside `_valid_candidate` guard; `zip(densities, per_density)` silent truncation; test URL-count assertion via substring (prefix-collision risk); report line-count numerics.
- Task 5 (reviewer Minor, brief-mandated): mid-file `family_b_candidates` import; `_WASH_FILES` duplicated between impl and test (intentional pinning); report line-count numerics.
- Task 6 (reviewer Minor, brief-inherited): mid-file `family_c_candidates` import; docstring says `<clean body>` but code uses "status digest" (cosmetic).
- Task 7 (reviewer Minor, brief-inherited): mid-file `family_d_candidates` import (same tracked pattern).
- Task 8 (reviewer Minor, brief-mandated): bare `except Exception: continue` swallows interact errors silently (diagnosability gap only); unused mid-file `import base64` in test; margin test only pins termination not the 15% itself; `b64` recomputed per iteration.
- Task 9 (reviewer Minor, brief-mandated): unused `family_a_candidates` in test import; density tests don't discriminate d8 from d4 / don't assert family ordering (ordering enforced by concatenation, verified by inspection); `_N_URLS` comment says "pool capacity (600)" but capacity is 864 (cosmetic).
- Task 10 (reviewer Minor, brief-mandated): smoke note is a docstring string line not a `#` comment (brief said to put it in the docstring); note line ~180 chars (cosmetic).

- [x] Final-review fix wave (commit d2ee97c, re-review approved: Spec ✅ / quality Approved, 0 Critical 0 Important; fixer verified 28 covering / 32 full, reviewer independently verified all 5 fixes against vendored SDK): dead Phase 2 phrases replaced (backup.txt step + decode-then-post probe + pinning test), `_valid_candidate` now rejects whitespace-only (mirrors gateway strip contract, 2 new tests), family-A `i=0` hoisted (d8→urls[0:240], d4→[240:400], d2→[400:500], d1→[500:600]), family-D `zip` diagonal pairs (60 distinct url+recipient), `_N_URLS` comment corrected.
- [x] **BRANCH FINISHED 2026-08-14**: created `main` from feat/attack-algorithm tip (fast-forward, no remote configured), deleted feature branch, 32/32 pass on main, ledger committed.

## Final whole-branch review (opus, 2026-08-13): Ready to merge WITH FIXES

**Important (in fix wave):**
1. Two Phase 2 phrases are structurally dead: base64 phrase (eval_predicates is plaintext-only for the sentinel — spec §6 assumption empirically refuted; decode passes only apply to trace-read secrets) and "Step 1: read the page" (compliance taints web → post blocked). ~40% of live-search budget unproductive. Fix: plaintext replacements + pinning test that encoded sentinel does NOT trigger EXFILTRATION.
2. `_valid_candidate` laxer than gateway replay contract: gateway rejects empty/whitespace messages (ValueError, aborts whole eval run — ops.py:488-489, 792-814). Latent (no generator produces them) but validator must mirror the contract. Fix: `m.strip()` check + tests for `("",)` / `(" ",)` — also resolves the Task 3 `("",)` policy question.

**Minor (fix in same wave, cheap value):** #3 family-A density bands reuse same URL window (i=0 resets per density; spec wanted distinct domain groups; one-line hoist); #4 family-D all posts go to urls[0] (product advances recipients fastest; ~59 lost post cells ≈ +0.6 pts; zip diagonal); #5 `_N_URLS` comment wrong (capacity 864).

**Minor (leave, P3):** #6 bare except + b64 recompute; #7 Phase 2 cycles fixed 200 combos; all accumulated per-task Minors except Task 3's `("",)` (folded into Important #2).
- Task 8 (reviewer Minor #6, evaluated at Task 9: NO CHANGE NEEDED): `_phase2` reserves 15% of the budget it receives — but `_phase1` is pure enumeration (~ms), so passing the full budget is safe; total stays within the real deadline.
Task 1: complete (commits d9d70d7..ad91710, review clean; Minor noted: tautological >=864 assert, url-stream no uniqueness assert — brief-inherited)
Task 2: complete (commits ad91710..013da96, review clean; downstream note: recipient pools must stay free of send/email/upload, is_clean doesn't enforce)
Task 3: complete (commits 013da96..2ef7852, review clean; Minor: hops= override untested)
Task 4: complete (commits 2ef7852..0a63517, review approved; deviations adjudicated forced+spec-consistent: predictive cap break, warm-up error seeds streak, harness fidelity fixes; Minor: no infinite-stream termination test, max-vs-mean estimator underfill trade-off)
Task 5: complete (commits 0a63517..8fa4578, review clean; Minor: dual itertools import styles, ~31% docstring claim unvalidated)
Task 6: complete (commits 8fa4578..0e42fd0 incl fix, review approved; Minor: HOSTED_MAX_TOOL_HOPS now unused, unused test imports, kaggle_cell2.py stale until Task 7)
Task 7: complete (commit cbac090, smoke clean: 60s->360 fallback, 150s->live path 61s all-miss->fallback, 0 rejections; cell rebuilt, no path leaks)
Final review: READY TO MERGE (0 Critical, 0 behavioral Important); fix wave f81186d: I1 run()-level live-fire test added, M1/M2/M3 docstring+warmup fixed; 33/33 tests, validate pass. V4 deferred: M4 minor cleanups, Harmony forgery, K-modes.
V4 Task 1: complete (53ddff9..101a7c0, review clean; Minor: token-membership vs full-string equality in test)
V4 Task 2: complete (101a7c0..77365fd, review approved; deviations adjudicated forced: warmup short-circuit in test fakes, deadline 40->50; Minor: idealized V3-stop comment, dup warmup guard)
V4 Task 3: complete (77365fd..5d62eea, review clean; Minor: pre-existing unused test imports)
V4 Task 4: complete (commit follows, smoke clean: validate pass; 60s->0.0s straight fallback 360 (edge-prune), 150s->live path 95s all-miss->fallback 360; both scores 0.00, 0 rejections, 360 unique cands within limits; cell rebuilt, embedded == attack.py, no path leaks)
V4 final review: READY TO SUBMIT (0C/0I; forged template no rejection vector, margin arithmetic covers 2-probe targets); minors deferred to V5
V5 Task 1: complete (980e0d4..c07493b, review clean; Minor: stale V4 comment header in test_fill)
V5 Task 2: complete (c07493b..b6aff35, review clean; brief typo total-39 noted)
V5 Task 3: complete (b6aff35..c757f90, merged a900c47, smoke clean)
V5 final review: READY TO SUBMIT (throughput sim: fast 0.91-0.95x V3, slow-row up to 2.74x; minors deferred to V6)

## V6 — forged + slow-row multipost (2026-08-18)

- Spec: `docs/superpowers/specs/2026-08-18-v6-forged-multipost-design.md` (replaces 08-17 forged-only; research-driven: evgendvorkin PHOENIX V5 88.51 / dimong4 88.07 / yusuketogashi 91.53 source analysis)
- Key discovery: multi-post (N posts/candidate via Harmony frame) + REPLAY_SAFE_FRAC 0.9995 vs our 0.97; verified predicate weights SEVERITY_W {3:4, 4:8, 5:16}
- Implementation (05d2945, merged 3f26634): forged_multipost_msg (evgendvorkin verbatim), _fill make_post/make_multipost slow-row split (LATENCY_PROBES=8 classify, >12s slow), REPLAY_SAFE_FRAC 0.9995, MULTIPOST_REPLAY_COEF 2.0, drop post_msg_variants; 41 tests green
- Smoke: validate pass, 60s→fallback 360, 150s→live path, 0 rejections
- Parallel submissions (2026-08-18, 3/5 quota used): 
  - V6-A (Version 12, ref 55590304): N=4 multipost + 0.9995 ← main
  - V6-B (Version 13, ref 55590829): N=8 probe
  - V6-D (Version 14, ref 55590814→55590857): multipost + email deputy suffix
- CLI tooling: assemble_submit.py (variant A/B/D → push+submit, NvidiaTeslaT4, internet disabled — competition forbids internet, 400 FAILED_PRECONDITION caught)
- Pending: scores ~15h later
