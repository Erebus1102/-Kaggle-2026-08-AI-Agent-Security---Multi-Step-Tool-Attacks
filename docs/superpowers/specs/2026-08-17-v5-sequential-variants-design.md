# V5 设计:顺序变体探测(plain-first,forged 作 miss 后备)

日期:2026-08-17
状态:已批准(用户 2026-08-17 确认)
前置:V4 spec(2026-08-16)、V4 线上结果 49.530(V3 为 52.370,回归 -2.84)

## 1. 背景与动机

V4 的"每 URL 双模板都探"被线上证伪:伪造模板带来的额外 fire 不足以抵偿 50% 探针吞吐损失。机制:未 fire 的探针消耗生成 wall-clock → 生成 deadline 内收集的 fired 候选减少 → 候选列表变短 → 回放窗口未填满。

**目标**:恢复 V3 吞吐(≥52.37),同时保留伪造模板对"gpt-oss 拒绝普通指令的 URL"的上行期权。

## 2. 设计

### 2.1 核心变更(仅 `_fill` 内层循环)

```
对每个 target:
  按 make_msgs(target) 的顺序逐个探测变体:
    fire → 收录该条,跳过该 target 剩余变体(break 内层)
    miss → 探下一个变体
    全 miss → 放弃该 target
```

- **first-fire-wins,每 target 最多收录 1 条候选**(V4 是都 fire 就都收)
- 依据:同 URL 的重复候选得 16 分但 0 novelty,而一个新 URL 得 16+2;重复候选还多耗一次探针——唯一覆盖严格占优
- warm-up 不变:仍用 `make_msgs(warmup_target)[0]`(普通模板)

### 2.2 保持不变(V4 中性/正向改动全部保留)

- 均值 edge-prune + `EDGE_MARGIN_FLOOR_S = 30.0`
- `MAIN_FRAC = 0.98`(deputy 2%)
- 伪造模板字符串逐字不变、`post_msg_variants` 顺序不变(plain 在前)
- `_probe` / `_static_fallback`(仍纯普通模板)/ streams / `_finalize` / 全部硬约束防线

### 2.3 预算语义

- 探针吞吐恢复:普通 fire 率为 p 时,每 target 期望探针数 = `1×p + 2×(1−p)`(V4 恒为 2;p=0.8 时 1.2 vs 2.0)
- 重放成本累计、edge-prune、错误 streak 语义全部不变(streak 仍跨变体累计,first-fire-wins 的 break 不清零也不跳过 streak 语义——clean miss/fire 重置,errored 累计)

## 3. 测试

1. first-fire-wins:两变体都 fire → 只收录 plain,伪造**未被探测**(探针计数断言)
2. miss-then-fire:plain miss、forged fire → 收录 forged
3. 全 miss → 无收录
4. 探针数:3 targets、全 miss、2 变体 → 恰好 6 次探针
5. `run()` 集成测试更新:fake env 全 fire → 每 URL 只留 plain(5 plain + 3 deputy = 8,无伪造消息)
6. 端到端:validate + deterministic 两档冒烟(预期 0 分)

## 4. 风险

1. 若 gpt-oss 行普通 fire 率低而伪造才是主得分通道,V5 在该行退化为 V4 行为(先耗一次 miss 探针)——可接受的下行保护
2. 生成 ≠ 回放漂移(V4 已暴露的可能性之一)在 V5 依然存在——若 V5 仍 <52,则基本锁定漂移解释,V6 回滚伪造模板
3. 每 target 1 条候选使列表更"稀",但 replay-safe 累计停机逻辑保证窗口仍被填满(以 fired 探针耗时累计为准)

## 5. 非目标(V6+)

延迟分流(jed-v25 式慢行专用伪造)、多消息 K 模式、措辞第三变体、private guardrail 对抗、模板统计倾斜。
