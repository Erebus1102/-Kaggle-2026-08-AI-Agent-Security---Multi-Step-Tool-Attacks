"""应用更新：备份 → 删除旧块 → 写入新块 → 验证。

用法：
  export NOTION_TOKEN=secret_xxx
  python3 apply_update.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

PAGE_ID = "392fa776-add4-805c-a495-ee4b584fe417"
API = "https://api.notion.com/v1"
NEW_CHILDREN = "/tmp/notion_new_children.json"
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup")


def req(method, path, body=None):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN 环境变量未设置")
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"HTTP {e.code} on {method} {path}: {detail}")


def backup_and_delete():
    """备份现有子块，然后逐个归档。"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    children = req("GET", f"/blocks/{PAGE_ID}/children?page_size=100")
    results = children.get("results", [])
    if not results:
        print("页面当前没有子块，跳过删除")
        return
    with open(os.path.join(BACKUP_DIR, "old_children.json"), "w") as f:
        json.dump(children, f, ensure_ascii=False, indent=1)
    print(f"已备份 {len(results)} 个旧块 -> backup/old_children.json")
    for i, blk in enumerate(results):
        bid = blk["id"]
        req("DELETE", f"/blocks/{bid}")
        time.sleep(0.4)
        if (i + 1) % 10 == 0:
            print(f"  已删除 {i + 1}/{len(results)}")
    print("旧块删除完成")


def append_new():
    with open(NEW_CHILDREN) as f:
        children = json.load(f)
    BATCH = 40  # Notion 单次请求上限 100，留余量
    for i in range(0, len(children), BATCH):
        batch = children[i : i + BATCH]
        req("PATCH", f"/blocks/{PAGE_ID}/children", {"children": batch})
        time.sleep(0.5)
        print(f"  已写入 {min(i + BATCH, len(children))}/{len(children)}")
    print("新块写入完成")


def verify():
    results = []
    cursor = None
    while True:
        url = f"/blocks/{PAGE_ID}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        page = req("GET", url)
        results.extend(page.get("results", []))
        if not page.get("has_more"):
            break
        cursor = page["next_cursor"]
        time.sleep(0.4)
    from collections import Counter
    types = Counter(b["type"] for b in results)
    print(f"\n验证：共 {len(results)} 个顶层块")
    print("类型分布:", dict(types.most_common()))
    # 抽查第一个表格的宽度与标题层级顺序
    for b in results[:12]:
        t = b["type"]
        if t in ("heading_2", "heading_3"):
            txt = "".join(x["plain_text"] for x in b[t]["rich_text"])
            print(f"  {t}: {txt}")
        elif t == "table":
            w = b["table"]["table_width"]
            rows = len(b["table"]["children"])
            print(f"  table: {w} 列 x {rows} 行")
    h2s = [b for b in results if b["type"] == "heading_2"]
    print(f"\n共 {len(h2s)} 个 H2 章节（应为 17）")
    assert len(h2s) == 17, "H2 数量不符！"
    print("验证通过 ✔")


if __name__ == "__main__":
    if "--verify-only" in sys.argv:
        verify()
    else:
        backup_and_delete()
        append_new()
        verify()
