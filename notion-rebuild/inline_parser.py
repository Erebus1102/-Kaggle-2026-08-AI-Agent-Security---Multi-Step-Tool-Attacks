"""行内 markdown -> Notion API rich_text 数组。

支持（非嵌套）：`code`、**bold**、*italic*、<https://url>。
"""
import re

TOKEN_RE = re.compile(
    r"(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(<https?://[^>\s]+>)"
)


def text_rt(content: str, *, link=None, code=False, bold=False, italic=False):
    rt = {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": False,
            "underline": False,
            "code": code,
            "color": "default",
        },
    }
    if link:
        rt["text"]["link"] = {"url": link}
    return rt


def parse_inline(md: str) -> list:
    """把一行含行内 markdown 的文本解析为 rich_text 列表。"""
    out = []
    pos = 0
    for m in TOKEN_RE.finditer(md):
        if m.start() > pos:
            plain = md[pos : m.start()]
            if plain:
                out.append(text_rt(plain))
        code_s, bold_s, ital_s, link_s = m.groups()
        if code_s is not None:
            out.append(text_rt(code_s[1:-1], code=True))
        elif bold_s is not None:
            out.append(text_rt(bold_s[2:-2], bold=True))
        elif ital_s is not None:
            out.append(text_rt(ital_s[1:-1], italic=True))
        elif link_s is not None:
            url = link_s[1:-1]
            out.append(text_rt(url, link=url))
        pos = m.end()
    if pos < len(md):
        out.append(text_rt(md[pos:]))
    return out


def plain_rt(text: str) -> list:
    return [text_rt(text)]
