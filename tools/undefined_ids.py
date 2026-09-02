#!/usr/bin/env python3
"""
undefined_ids.py — یافتن شناسه‌های استفاده‌شده ولی تعریف‌نشده در اسکریپت Pine.

این ابزار کامپایلر TradingView نیست؛ فقط با تحلیل ایستا، نام‌هایی را که نه
تعریف شده‌اند و نه در فهرست داخلی Pine هستند گزارش می‌کند تا خطاهای
«undefined identifier» ناشی از غلط املایی قبل از درج در Pine Editor گرفته شود.

نکات پیاده‌سازی:
  • عبارت‌های چندخطی (ادامه‌یابی با تورفتگی) قبل از تحلیل به یک خط چسبانده
    می‌شوند تا تعریف‌های tuple و تابع چندخطی هم دیده شوند.
  • شناسه‌ای که قبل یا بعد از آن «.» باشد عضو یک namespace است و نادیده
    گرفته می‌شود.
  • نام‌های داخل رشته‌ها و کامنت‌ها حذف می‌شوند.

استفاده:
    python3 tools/undefined_ids.py <file.pine>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BUILTIN_PLAIN = {
    "open", "high", "low", "close", "volume", "time", "timenow", "bar_index",
    "hl2", "hlc3", "ohlc4", "last_bar_time", "last_bar_index", "dayofmonth",
    "dayofweek", "month", "year", "hour", "minute", "second", "weekofyear",
    "na", "true", "false", "int", "float", "bool", "string", "color",
    "line", "label", "box", "table", "array", "map", "matrix",
}

BUILTIN_NS = {
    "math", "str", "array", "matrix", "map", "input", "request", "ta", "ticker",
    "timeframe", "color", "line", "label", "box", "table", "polyline", "chart",
    "syminfo", "display", "extend", "xloc", "yloc", "size", "shape", "location",
    "position", "text", "session", "alert", "barmerge", "format", "scale",
    "barstate", "linefill", "runtime", "strategy",
}

NAMED_ARGS = {
    "minval", "maxval", "step", "inline", "title", "width", "group", "tooltip",
    "text_color", "text_halign", "text_valign", "border_width", "border_color",
    "frame_color", "frame_width", "bgcolor", "color", "style", "size",
    "location", "extend", "xloc", "yloc", "display", "linewidth", "precision",
    "overlay", "format", "shorttitle", "max_bars_back", "max_lines_count",
    "max_labels_count", "max_boxes_count", "gaps", "lookahead", "options",
    "confirm", "editable", "defval", "textcolor", "trackprice", "show_last",
    "char", "offset", "join", "wrap", "behind_chart", "bars_back",
}

KEYWORDS = {
    "and", "or", "not", "if", "else", "for", "while", "to", "by", "var",
    "varip", "switch", "import", "export", "type", "method", "series", "simple",
    "const", "input", "indicator", "strategy", "library", "plot", "plotshape",
    "plotchar", "plotarrow", "plotbar", "plotcandle", "hline", "fill",
    "bgcolor", "alertcondition", "max_bars_back", "barmerge",
}

TYPES = {"int", "float", "bool", "string", "color", "line", "label", "box",
         "table", "linefill", "polyline", "chart", "source", "series", "simple",
         "const", "input"}

FUNC_DEF_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
FUNC_DEF_ARROW_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=>")
DECL_RE = re.compile(
    r"^\s*(?:(?:var|varip)\s+)?(?:(?:series|simple|const|input)\s+)?"
    r"(?:(?:int|float|bool|string|color|line|label|box|table|array<[^>]*>|map<[^>]*>)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=(?!=))"
)
TUPLE_RE = re.compile(r"^\s*\[([^\]]+)\]\s*=(?!=)")
FOR_RE = re.compile(r"^\s*for\s+(?:(?:int|float)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
IDENT_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")


def strip_hex(line: str) -> str:
    line = re.sub(r"#[0-9A-Fa-f]{3,8}", " 0 ", line)
    line = re.sub(r"\b\d+\.?\d*[eE][-+]?\d+\b", " 0 ", line)
    return line


def strip_strings(line: str) -> str:
    out, in_str, i = [], None, 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            out.append(" ")
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def logical_lines(src: str) -> list[tuple[int, str]]:
    """چسباندن خطوط ادامه‌دار به خط منطقی (با شماره خطِ شروع)."""
    result: list[tuple[int, str]] = []
    pending_no = 0
    pending = ""
    for no, raw in enumerate(src.split("\n"), start=1):
        if raw.strip().startswith("//"):
            if pending:
                result.append((pending_no, pending))
                pending, pending_no = "", 0
            continue
        stripped = raw.rstrip()
        if not stripped.strip():
            if pending:
                result.append((pending_no, pending))
                pending, pending_no = "", 0
            continue
        indent = len(stripped) - len(stripped.lstrip())
        open_brackets = pending.count("[") - pending.count("]") + \
            pending.count("(") - pending.count(")")
        if pending and (indent >= 5 or open_brackets > 0):
            pending += " " + stripped.strip()
            continue
        if pending:
            result.append((pending_no, pending))
        pending, pending_no = stripped, no
    if pending:
        result.append((pending_no, pending))
    return result


def collect_params(text: str) -> set[str]:
    names: set[str] = set()
    for chunk in re.finditer(r"\(([^()]*)\)", text):
        for part in chunk.group(1).split(","):
            part = part.strip()
            m = re.match(r"^(?:var\s+)?(?:(?:series|simple|const|input)\s+)?"
                         r"(?:(?:int|float|bool|string|color|line|label|box|table|source|array<[^>]*>)\s+)"
                         r"([A-Za-z_][A-Za-z0-9_]*)", part)
            if m:
                names.add(m.group(1))
    return names


def main(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    lines = logical_lines(src)

    declared: set[str] = (set(BUILTIN_PLAIN) | set(BUILTIN_NS) | set(KEYWORDS) |
                          TYPES | NAMED_ARGS)
    used: dict[str, list[int]] = {}

    # تعریف‌ها از هر خط خام (با هر تورفتگی) جمع می‌شوند تا متغیرهای محلیِ
    # داخل بلوک‌ها هم دیده شوند.
    for no, raw in enumerate(src.split("\n"), start=1):
        if raw.strip().startswith("//"):
            continue
        code = strip_hex(strip_strings(raw))
        m = FUNC_DEF_RE.match(code)
        if m and "input." not in code and m.group(1) not in TYPES:
            declared.add(m.group(1))
            declared |= collect_params(code)
        m = FUNC_DEF_ARROW_RE.match(code)
        if m:
            declared.add(m.group(1))
        m = DECL_RE.match(code)
        if m:
            declared.add(m.group(1))
        m = TUPLE_RE.match(code)
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                part = re.sub(r"^(?:var|varip)\s+", "", part)
                part = re.sub(r"^(?:int|float|bool|string|color|line|label|box|table|"
                              r"array<[^>]*>|map<[^>]*>)\s+", "", part)
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
                    declared.add(part)
        m = FOR_RE.match(code)
        if m:
            declared.add(m.group(1))
        for chunk in re.finditer(r"\(([^()]*)\)", code):
            for part in chunk.group(1).split(","):
                mm = re.match(r"^\s*(?:var\s+)?(?:(?:int|float|bool|string|color|line|label|box|table)\s+)"
                              r"([A-Za-z_][A-Za-z0-9_]*)\s*=", part)
                if mm:
                    declared.add(mm.group(1))

    for no, text in lines:
        code = strip_strings(text)
        m = FUNC_DEF_RE.match(code)
        if m and "input." not in code and m.group(1) not in TYPES:
            declared.add(m.group(1))
            declared |= collect_params(code)
        m = FUNC_DEF_ARROW_RE.match(code)
        if m:
            declared.add(m.group(1))
        m = DECL_RE.match(code)
        if m:
            declared.add(m.group(1))
        m = TUPLE_RE.match(code)
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                part = re.sub(r"^(?:var|varip)\s+", "", part)
                part = re.sub(r"^(?:int|float|bool|string|color|line|label|box|table|"
                              r"array<[^>]*>|map<[^>]*>)\s+", "", part)
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
                    declared.add(part)
        m = FOR_RE.match(code)
        if m:
            declared.add(m.group(1))

    # پاس دوم روی خطوط منطقی: امضای توابع چندخطی
    for no, text, *_ in [(a, b) for a, b in lines]:
        code = strip_hex(strip_strings(text))
        m = FUNC_DEF_RE.match(code)
        if m and m.group(1) not in TYPES:
            declared.add(m.group(1))
            declared |= collect_params(code)

    for no, text in lines:
        code = strip_hex(strip_strings(text))
        for tok in IDENT_RE.finditer(code):
            name = tok.group(1)
            before = code[tok.start() - 1] if tok.start() > 0 else ""
            after = code[tok.end()] if tok.end() < len(code) else ""
            if before == "." or after == ".":
                continue
            if name in declared:
                continue
            used.setdefault(name, []).append(no)

    if not used:
        print(f"OK — هیچ شناسه تعریف‌نشده‌ای در {path.name} یافت نشد.")
        return 0

    print(f"⚠ {len(used)} شناسه مشکوک در {path.name}:")
    for name, idxs in sorted(used.items()):
        print(f"   {name:26s} خطوط {idxs[:8]}{' ...' if len(idxs) > 8 else ''}")
    return 1


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/SMC_NTS_PRO_v6.pine")
    sys.exit(1 if main(target) else 0)
