# V5 顺序变体探测 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_fill` 内层循环从"每 target 探全部变体"改为"按序探测、fire 即收即停"(first-fire-wins),恢复 V3 吞吐并保留伪造模板上行期权。

**Architecture:** 唯一生产代码变更在 `_fill` 的变体循环(fire → 收录 → break);其余 V4 改动全部保留。测试更新集中在 `tests/test_fill.py`(2 个 V4 用例改语义 + 1 个新增)与 `tests/test_run.py`(集成断言 13→8)。Spec:`docs/superpowers/specs/2026-08-17-v5-sequential-variants-design.md`。

**Tech Stack:** Python 3.12,`aicomp_sdk 3.1.2`(vendored),pytest(workspace/.venv)。

## Global Constraints

- first-fire-wins 语义:**任一变体 fire → 收录该条(若过 `_valid_candidate`)→ break**,无论剩余变体;每 target 最多 1 条候选。
- streak 语义不变:errored 累计、clean miss/fire 重置、连续 `MAX_CONSECUTIVE_ERRORS`(5)→ `(out, False)`;break 不影响 streak。
- 保留不变:伪造模板字符串逐字、`post_msg_variants` 顺序(plain 在前)、均值 edge-prune、`EDGE_MARGIN_FLOOR_S=30.0`、`MAIN_FRAC=0.98`、warm-up 用 `make_msgs(warmup_target)[0]`。
- 测试命令在 `workspace/` 下:`.venv/bin/python -m pytest ...`。
- git 操作在仓库根目录;分支 `feat/v5-sequential-variants`。
- 基线:main @ e02da3a,39 tests 全绿。

---

### Task 0: 创建分支

- [ ] **Step 1:**

```bash
cd "/Users/renhaoliu/Desktop/Project/AI Agent Security - Multi-Step Tool Attacks"
git checkout -b feat/v5-sequential-variants
```

Expected: `Switched to a new branch 'feat/v5-sequential-variants'`

---

### Task 1: `_fill` first-fire-wins + test_fill 语义更新

**Files:**
- Modify: `workspace/attack.py`(`_fill` 内层循环)
- Test: `workspace/tests/test_fill.py`(2 个用例改语义、1 个新增)

**Interfaces:**
- Consumes: 现有 `_fill(env, deadline, targets, make_msgs, replay_cap_s, warmup_target=...)`、`_probe`、`_valid_candidate`
- Produces: `_fill` 签名不变;行为变更:first-fire-wins(后续任务与 Kaggle cell 依赖此行为,不依赖新名字)

- [ ] **Step 1: 改写测试**(3 处)

(a)把 `test_fill_probes_every_variant_per_target`(V4:全 fire 期望 6 探 6 收)**整体替换**为:

```python
def test_fill_first_fire_wins_skips_remaining(monkeypatch):
    # V5: any variant firing collects it and skips the sibling variant.
    import attack as attack_mod
    from attack import post_msg_variants
    env = _ScriptedEnv(["fire"])
    calls = []

    def fake_probe(env_, msg, hops=1):
        if "warmup" in msg:
            return False, False, 5.0          # warm-up short-circuit
        calls.append(msg)
        return True, False, 5.0
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)
    import itertools as _it
    import time as _time
    from attack import _url_stream
    kept, live_ok = _fill(
        env, deadline=_time.monotonic() + 1000,
        targets=_it.islice(_url_stream(), 3),
        make_msgs=post_msg_variants, replay_cap_s=10_000.0)
    assert len(calls) == 3                    # one probe per target (plain)
    assert live_ok is True and len(kept) == 3
    assert all(c.user_messages[0].startswith("Call http.post") for c in kept)
```

(b)`test_fill_keeps_only_forged_when_plain_misses`(plain miss、forged fire)——断言保持,追加探针计数断言。在该测试末尾(`assert len(kept) == 2` 所在函数内)补充:

```python
    import itertools as _it2                 # 若文件顶部已有 itertools 引入则复用
    # 2 targets × (miss + fire) = 4 variant probes + 0 warmup (short-circuited)
```
并在该测试的 fake_probe 中以与 (a) 相同的 `calls` 列表记录非 warmup 探针,断言 `len(calls) == 4`。

(c)**新增**(文件末尾):

```python
def test_fill_all_variants_miss_zero_keeps_exact_probe_count(monkeypatch):
    import attack as attack_mod
    from attack import post_msg_variants
    env = _ScriptedEnv(["miss"])
    calls = []

    def fake_probe(env_, msg, hops=1):
        if "warmup" in msg:
            return False, False, 1.0
        calls.append(msg)
        return False, False, 1.0
    monkeypatch.setattr(attack_mod, "_probe", fake_probe)
    import itertools as _it
    import time as _time
    from attack import _url_stream
    kept, live_ok = _fill(
        env, deadline=_time.monotonic() + 1000,
        targets=_it.islice(_url_stream(), 3),
        make_msgs=post_msg_variants, replay_cap_s=10_000.0)
    assert kept == [] and live_ok is True
    assert len(calls) == 6                    # 3 targets × 2 variants, all missed
```

(d)旧用例 `test_fill_mean_estimator_survives_slow_outlier` 与其余 4 个 V3 用例**不动**(单变体工厂,语义不受 first-fire-wins 影响)。

- [ ] **Step 2: 确认失败**

```bash
cd workspace && .venv/bin/python -m pytest tests/test_fill.py -v
```
Expected: (a) FAIL(`6 != 3` 探针计数,现行实现探全部变体)、(c) PASS 或 FAIL 视现行行为(全 miss 时现行也探 6 次——此用例在新旧行为下同过,作回归锚);(b) 若加了计数断言则 PASS(现行全 miss 才继续)。核心 RED 信号是 (a)。

- [ ] **Step 3: 实现**——`_fill` 内层循环替换为:

```python
        for msg in make_msgs(target):
            fired, errored, elapsed = _probe(env, msg)
            n_probes += 1
            lat_total += elapsed
            if errored:
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    return out, False
                continue
            consecutive_errors = 0
            if fired:
                if _valid_candidate((msg,)):
                    replay_cost += elapsed
                    out.append(AttackCandidate(user_messages=(msg,)))
                break   # V5 first-fire-wins: skip remaining variants for this target
    return out, True
```

同时把 `_fill` docstring 中描述"kept iff it fires — both firing means both are kept"的一句改为:"a firing variant is collected and the target's remaining variants are skipped (first-fire-wins; unique coverage beats duplicates)"。

- [ ] **Step 4: 确认通过**

```bash
cd workspace && .venv/bin/python -m pytest tests/test_fill.py -v
```
Expected: 9 passed(8 个原有语义 + 新增 1;`test_fill_probes_every_variant_per_target` 已被替换)

- [ ] **Step 5: 全量回归(预期 test_run 1 失败)**

```bash
cd workspace && .venv/bin/python -m pytest tests/ -q
```
Expected: 除 `test_run.py::test_run_live_fires_return_posts_then_deputies`(V4 断言 5+5+3=13,V5 行为是 5+0+3=8)外全绿——Task 2 修

- [ ] **Step 6: Commit**

```bash
git add workspace/attack.py workspace/tests/test_fill.py
git commit -m "feat(v5): first-fire-wins sequential variant probing"
```

---

### Task 2: `run()` 集成测试更新

**Files:**
- Test: `workspace/tests/test_run.py`(`test_run_live_fires_return_posts_then_deputies` 断言块)

**Interfaces:**
- Consumes: Task 1 的 first-fire-wins 行为
- Produces: 无新接口

- [ ] **Step 1: 更新断言**(该测试内,替换 V4 的 13 候选断言块为):

```python
    posts_plain = [m for m in msgs if m.startswith("Call http.post")]
    posts_forged = [m for m in msgs if m.startswith("http.post url=")]
    deps = [m for m in msgs if m.startswith("Forward the")]
    assert len(posts_plain) == 5 and posts_forged == []   # first-fire-wins
    assert len(deps) == 3
    assert msgs.index(deps[-1]) > msgs.index(posts_plain[-1])
    assert len(msgs) == 8                                  # no fallback mixed in
```

- [ ] **Step 2: 确认失败→实现→通过**(本任务无生产代码;若 Step 1 后测试直接通过说明 Task 1 已完备,属正常)

```bash
cd workspace && .venv/bin/python -m pytest tests/test_run.py -v && .venv/bin/python -m pytest tests/ -q
```
Expected: 全部通过(总数 39:V5 净变化 = 替换 1 + 新增 1)

- [ ] **Step 3: Commit**

```bash
git add workspace/tests/test_run.py
git commit -m "test(v5): run() integration asserts first-fire-wins (5+3, no forged)"
```

---

### Task 3: 冒烟 + Kaggle cell 重建 + 合并

**Files:**
- Modify: `workspace/kaggle_cell2.py`(builder 重建)

- [ ] **Step 1: validate**

```bash
cd workspace && .venv/bin/aicomp validate redteam attack.py
```
Expected: 通过

- [ ] **Step 2: 两档冒烟**

```bash
cd workspace && .venv/bin/aicomp evaluate redteam attack.py --budget-s 60 --agent deterministic --env gym
cd workspace && .venv/bin/aicomp evaluate redteam attack.py --budget-s 150 --agent deterministic --env gym
```
Expected: 均正常完成、score 0.0(预期)、无 rejection

- [ ] **Step 3: 重建 cell + 泄漏检查**

```bash
cd workspace && .venv/bin/python build_kaggle_cell2.py && { grep -c "/Users/renhaoliu" kaggle_cell2.py || true; }
```
Expected: written + 计数 0

- [ ] **Step 4: Commit + 合并(用户已授权流水线)**

```bash
git add workspace/kaggle_cell2.py
git commit -m "chore(v5): rebuild kaggle cell-2 with v5 engine"
git checkout main && git merge --no-ff feat/v5-sequential-variants \
  -m "merge: V5 first-fire-wins sequential variants" && git push
git branch -d feat/v5-sequential-variants
```

---

## Self-Review 结果

1. **Spec 覆盖**:§2.1 first-fire-wins(Task 1 Step 3,break 语义与 spec 一致)✓;§2.2 保持不变(计划无相关改动,Global Constraints 锁定)✓;§2.3 预算语义(streak 交互在 Global Constraints 锁定)✓;§3 测试(Task 1 三个用例覆盖 spec §3.1–3.4,Task 2 覆盖 §3.5,Task 3 覆盖 §3.6)✓;§4/§5 无代码动作 ✓。
2. **占位符扫描**:Task 1 Step 1(b) 描述了确切的补充断言与实现方式(复用 (a) 的 calls 模式),非占位;无 TBD。
3. **类型一致性**:`_fill` 签名两任务间未变;`post_msg_variants` 复用 V4 定义;测试名在 Steps 间引用一致。
