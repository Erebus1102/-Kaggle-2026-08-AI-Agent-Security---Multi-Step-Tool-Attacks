# V7 设计:分流模板修正(gemma plain / gpt_oss multi4 + 会计修正)

日期:2026-08-19
状态:待批准
前置:V6 结果复盘、Ollama Cloud 本地真实模型测试、预测模型自洽验证

## 1. 背景与动机

Ollama Cloud 本地测试(gpt-oss:20b + gemma4:31b,llama.cpp 后端,与竞赛同后端)揭示了 V6-A 降分的两个根因,而预测模型现在精确命中所有已知分数:

```
探针 D 65.2      = forged 单 post + gemma_fire 0.75  (预测 63.4)  ✓
evgendvorkin 88.5 = multi4 + gemma_fire 1.0          (预测 88.5)  ✓ 精确命中
V6-A 58.7         = 两个错误叠加
```

### V6-A 的两个错误

1. **gemma 行用了 forged**(密度 3.14 raw/s),而 plain 密度 4.93(快 57%)。evgendvorkin/jed-v25 都用 "verbose gemma",我们是唯一用 forged 的。
2. **multi4 的 replay_cost × 2.0 会计错误**:probe 用 hops=1 只测 1 post(~4s),×2=8s 会计,但回放 4-post 实际 ~11.8s → 低估 32% → 候选数过多 → 回放超时截断。

### 本地实测(5 次中位数,fire rate 可靠)

| 模板 | gemma fire | gpt_oss fire |
|---|---|---|
| plain 单 post | 5/5,密度 4.93 | 5/5,密度 2.22 |
| forged 单 post | 5/5,密度 3.14 | 5/5,密度受负载波动(过载) |
| forged multi4 | 4 post,密度 5.65 | 4 post,密度 5.43 |

**multi4 在两个模型都执行 4 post(不漂移),理论密度 5.4-5.8 比单 post 高 33%。**

## 2. 设计(三个改动)

### 2.1 gemma(fast 行)用 plain 单 post

`_fill` 的 fast 行消息工厂从 `forged_post_msg` 改为 `post_msg`(plain verbose)。slow 判定逻辑不变(前 8 探针测延迟,>12s 判 slow)。

实现:新增一个按行选择模板的机制。最简:run() 主填充传一个"按 slow 标志选择"的工厂,或 _fill 增加 `make_fast`/`make_slow` 两个工厂参数。

### 2.2 gpt_oss(slow 行)保持 forged multi4

slow 行继续 `forged_multipost_msg`(已验证 4 post,密度 5.43)。

### 2.3 replay_cost 系数 2.0 → 1.0

`MULTIPOST_REPLAY_COEF` 从 2.0 改为 **1.0**。理由:probe 用 hops=1 测的是 1 post 时间(~4s),但 replay_cost 的语义是"回放成本"。当前会计把 1-post 时间 ×2 当 4-post 时间,低估。改 1.0 后会计 ≈ 1-post 时间,配合回放窗口的 fill_fraction 一起校准(或后续用实测 4-post 时间作为 replay_cost)。

**注意**:更精确的方案是 probe multi4 时用 hops=8 测完整 4-post 时间作为 replay_cost,但会增加 probe 成本。V7 先用 coef=1.0(保守,少候选不超时),V8 再考虑 hops=8 probe。

### 2.4 REPLAY_SAFE_FRAC 回退 0.97

V6-A 用了 0.9995,但 V6-A 降分无法分离 0.9995 的独立影响。V7 回退到 0.97(探针 D 验证过的安全值),与 multi4 的会计修正分离变量。V8 再单独测 0.9995。

## 3. 保持不变

- forged 模板字符串、forged_multipost_msg 逐字不变
- 均值 edge-prune、EDGE_MARGIN_FLOOR_S、MAIN_FRAC=0.98(deputy 2%)
- _probe / _finalize / streams / 静态兜底 plain / 硬约束防线

## 4. 预期

| 行 | 模板 | 密度 | 预期 normalized |
|---|---|---|---|
| gemma | plain 单 post | 4.93 | ~102(vs forged 的 ~65) |
| gpt_oss | forged multi4 | 5.43 | ~94 |

**预期 mean ≈ 88-98,对标 evgendvorkin 88.5。**

## 5. 测试

1. `_fill` 新增 fast/slow 模板工厂参数:fast 用 post_msg,slow 用 forged_multipost_msg
2. 单元测试:fast 行(slow=False)产出 plain 消息;slow 行产出 multi4 消息
3. `MULTIPOST_REPLAY_COEF == 1.0` 常量断言
4. 集成测试:fake env 模拟 fast → 全 plain;模拟 slow → multi4
5. 端到端:validate + deterministic 冒烟

## 6. 风险与判定树

1. **gemma plain vs forged 的线上差异**:Ollama Cloud 31b 显示 plain 快 57%,但线上 26b 可能不同。若 V7 gemma 行没提升,说明 26b 的 plain/forged 差异与 31b 不同,回退 forged。
2. **replay_cost 1.0 可能过保守**(候选数少),但保守不超时比激进超时安全。
3. **判定树**(V7 出分):
   - ≥85:分流模板 + 会计修正成立,V8 攻 REPLAY_SAFE_FRAC 0.9995 + hops=8 probe
   - 70-85:部分成立,继续差分定位
   - <70:gemma plain 假设在 26b 不成立,回退 forged,重心转 multi4 单独验证
