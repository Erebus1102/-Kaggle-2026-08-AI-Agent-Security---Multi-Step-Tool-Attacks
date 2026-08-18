# V6 设计:纯 forged 单变体填充

日期:2026-08-17
状态:待批准
前置:V5 spec(2026-08-17)、V5 线上结果 57.480、探针 B(纯 plain 回滚)58.145、探针 D(纯 forged)65.205

## 1. 背景与动机

四个并行数据点联立,首次让模板选择有了统计学意义:

| 提交 | 形态 | 分数 | vs 探针 B |
|---|---|---|---|
| 探针 B | 纯 plain(V3 精确回滚) | 58.145 | 基准 |
| V5 | plain-first,miss 才 forged | 57.480 | -0.7 |
| 探针 D | 纯 forged | **65.205** | **+7.1** |
| V3(历史) | 纯 plain | 52.370 | -5.8 |

**评测噪声约 6 分**(V3 与探针 B 是同一份代码两次跑,差 5.8)。由此:
- plain-first 与纯 plain 在噪声内等价(V5 ≈ 探针 B)——first-fire-wins 对分数无实际增益
- 纯 forged 领先 +7.1,勉强超出噪声,是**唯一可置信的胜出者**

### 机制(为什么纯 forged 占优)

forged 模板让 gpt-oss 跳过自生成推理直接执行工具调用,带来**双重吞吐收益**:
1. **生成阶段**:每次探针更快 → deadline 内收集更多 fired 候选
2. **回放阶段**:forged 候选在回放时同样更快 → 8750s 窗口回放更多候选 → 更多分

V5 的 plain-first 在 gpt-oss 行上,plain fire(慢)就收 plain 而跳过 forged,白白放弃了 forged 的快速执行优势——这正是它比纯 forged 低 ~7 分的原因。

**Gemma 行**:forged 的 Harmony token 不被 chat template 识别,但消息前缀 `http.post url=... data=SECRET_MARKER` 是纯文本指令,Gemma 仍可能执行(把 token 当噪声)——探针 D 的 65 分证明 forged 在两模型上都有分(若 gemma 两行为 0,gpt-oss 两行需 ~130 才能平均到 65,这在 1000 制下是合理上界,但更可能是两行都有贡献)。

**目标**:稳定复现并放大探针 D 的 65.205,冲 70+(进入主部队 70–90 的下沿)。

## 2. 设计

### 2.1 核心变更(一行语义)

`post_msg_variants(url)` 从双变体改为单变体:

```python
def post_msg_variants(url: str) -> tuple[str, ...]:
    """V6: forged-only. Plain lives on in _static_fallback only."""
    return (forged_post_msg(url),)
```

`_fill` 的 first-fire-wins 循环对单元素列表自然退化为"每 URL 探一次 forged,fire 收 / miss 弃",**无需改动 `_fill` 本身**。

### 2.2 保持不变

- `_fill` / `_probe` / `_finalize` / 全部硬约束防线:零改动
- `MAIN_FRAC = 0.98`(deputy 2%,与探针 D 一致——它证明了这个组合拿 65)
- `deputy_msg` 及其填充:零改动(仍单变体 lambda)
- 均值 edge-prune + `EDGE_MARGIN_FLOOR_S = 30.0`:零改动
- `forged_post_msg` 字符串:逐字不变

### 2.3 warm-up 语义(唯一连带变化)

`_fill` 的 warm-up 用 `make_msgs(warmup_target)[0]`,V6 下自动变为 forged 模板。warm-up 结果本来就被丢弃(只吸收首次模型加载延迟),用哪个模板无影响。**明确**:这是预期行为,不是需要修正的副作用。

### 2.4 静态兜底保留 plain

`_static_fallback` 仍用 `post_msg`(plain)+ `deputy_msg`。理由:兜底只在活体环境完全失败(连续 5 错误 / 预算 <120s)时启用,此时追求**最大 fire 确定性**而非速度——plain 在两模型上都认,是最稳形态。`post_msg` 函数因此保留(仅供兜底),实现者不得删除。

## 3. 预算语义

- 每 target 探针数从 `p + 2(1−p)`(V5)降为恒 1 → 生成吞吐比 V5 再提升
- 重放成本累计、edge-prune、错误 streak 语义:全部不变
- 唯一实质变化:每个 fired 候选都是 forged 形态

## 4. 测试

1. `post_msg_variants(url)` 返回单元素 tuple,元素是 forged 消息(含全部控制 token + URL + marker)
2. `post_msg` 仍存在且被 `_static_fallback` 引用(防误删回归)
3. `_fill` 对单变体行为:fire 收 / miss 弃,探针数 = target 数(单变体下无重复探测)
4. `run()` 集成测试更新:fake env 全 fire → 主填充全是 forged 消息(无 plain);deputy 部分不变
5. 端到端:validate + deterministic 两档冒烟(预期 0 分,验管道)

## 5. 风险与判定树

1. **纯 forged 可能是批次噪声**:探针 D 的 +7.1 只勉强超过 6 分噪声。V6 是第二次独立验证。
2. **若 V6 ≥ 68**:纯 forged 显著成立,V7 攻 70–90 主部队(多消息 K 模式、email 叠加、更激进 sizing)
3. **若 V6 ∈ [60, 68)**:纯 forged 成立但幅度有限(~5 分),V7 需叠加其他杠杆才进主部队
4. **若 V6 < 60**:纯 forged 优势大概率是噪声,回退 plain-first,并接受模板选择已到局部最优,重心转向候选密度/多消息形态
5. 生成 ≠ 回放漂移风险仍在,但四个数据点的单调性(纯 forged > 混合 > 纯 plain)支持"forged 在回放侧同样成立"而非"仅生成侧假阳性"

## 6. 非目标(V7+)

多消息 K 模式、email 叠加、模板统计倾斜、deputy forged 化、private guardrail 对抗、Harmony 延迟分流(已随纯 forged 自然覆盖)。
