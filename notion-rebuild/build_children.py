"""把 content_spec.OPS 转换为 Notion API children JSON。

用法：python3 build_children.py [输出路径]   # 默认 /tmp/notion_new_children.json
"""
import json
import sys

from inline_parser import parse_inline, plain_rt
from content_spec import OPS

TYPE_TO_KEY = {
    "p": "paragraph",
    "bl": "bulleted_list_item",
    "nl": "numbered_list_item",
    "quote": "quote",
    "h2": "heading_2",
    "h3": "heading_3",
    "code": "code",
    "table": "table",
}


def build() -> list:
    children = []
    for op in OPS:
        kind = op[0]
        if kind == "table":
            rows = op[1]
            width = len(rows[0])
            table_rows = []
            for row in rows:
                assert len(row) == width, f"row width mismatch: {row}"
                cells = [[rt for rt in parse_inline(cell)] for cell in row]
                table_rows.append({"type": "table_row", "table_row": {"cells": cells}})
            children.append({
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": width,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": table_rows,
                },
            })
        elif kind == "code":
            _, language, content = op
            children.append({
                "object": "block",
                "type": "code",
                "code": {"rich_text": plain_rt(content), "language": language},
            })
        else:
            key = TYPE_TO_KEY[kind]
            text = op[1]
            children.append({
                "object": "block",
                "type": key,
                key: {"rich_text": parse_inline(text)},
            })
    return children


def validate(children: list):
    """自检：无字面 markdown 残留、表格行列一致。"""
    import re

    def walk(block):
        yield block
        for key in ("children",):
            for sub in block.get(key, []):
                yield from walk(sub)

    for b in children:
        for sub in walk(b):
            rich_key = sub.get("type")
            rt_list = sub.get(rich_key, {}).get("rich_text")
            if not rt_list:
                continue
            for rt in rt_list:
                txt = rt["text"]["content"]
                ann = rt["annotations"]
                # 代码 span 内允许任意字符；其余文本不应残留 markdown 符号
                if ann["code"]:
                    continue
                bad = re.findall(r"[*`]|<https?://", txt)
                if bad:
                    raise SystemExit(f"markdown residue in {txt!r}: {bad}")
    print(f"OK: {len(children)} top-level blocks, all clean")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/notion_new_children.json"
    children = build()
    validate(children)
    with open(out_path, "w") as f:
        json.dump(children, f, ensure_ascii=False, indent=1)
    print(f"written to {out_path}")
