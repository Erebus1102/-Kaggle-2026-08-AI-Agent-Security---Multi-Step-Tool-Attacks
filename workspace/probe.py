import os
from pathlib import Path

from aicomp_sdk.evaluation.ops import build_attack_env # 搭建沙箱的函数
from aicomp_sdk.agents.deterministic_agent import VulnerableDeterministicAgent  # 受害者
from aicomp_sdk.guardrails.base import GuardrailBase # 假 guardrail：永远放行
from aicomp_sdk.guardrails.optimal import Guardrail as OptimalGuardrail # 真 guardrail
from aicomp_sdk.core.predicates import eval_predicates # # 计分用的谓词判定，就是把"受害者 / 防御 / 评分"三块零件 import 进来

FIXTURES = (
    Path(os.environ["AICOMP_ROOT"]) / "aicomp_sdk" /
"fixtures"
)
# ← 假数据（24文件/网页/邮件）的路径


def run(message, guardrail, hops=8):
    env = build_attack_env(
        seed=123,
        fixtures_dir=FIXTURES,
        agent_factory=lambda: VulnerableDeterministicAgent(),
        guardrail=guardrail,
        env_selection="sandbox",
        max_tool_hops=hops,
    ) # ① 用指定的 agent + guardrail + 假数据，拼一个沙箱
    env.reset() # ② 清空到初始状态
    env.interact(message, max_tool_hops=hops) # ③ 把消息发给agent，它最多做 8 轮工具调用
    tr = env.export_trace_dict() # ④ 取出"刚才发生了什么"的日志，叫 trac
    gname = type(guardrail).__name__
    print()
    print(f"=== {message!r} | guardrail={gname} ===") # ⑤ 把日志一行行打印 + 跑 eval_predicates 看违规没
    for e in tr["tool_events"]:
        name = str(e.get("name"))
        ok = str(e.get("ok"))
        side = str(e.get("side_effect"))
        src = str(e.get("source"))
        print(
            f"  {name:11} ok={ok:5} side={side:7}",
            f"src={src:6} args={e.get('args')}",
            f"err={e.get('error')}",
        )
    preds = eval_predicates(tr)
    print("  --> predicates:", preds or "(none)")


if __name__ == "__main__":
    MSG = "open page_1035"
    run(MSG, GuardrailBase())
    run(MSG, OptimalGuardrail())