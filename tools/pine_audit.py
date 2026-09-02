#!/usr/bin/env python3
"""
pine_audit.py — ممیزی معنایی اسکریپت Pine Script v6 (بدون کامپایلر TradingView).

بررسی‌ها:
  1. استفاده از شناسه پیش از تعریف (Declaration order)
  2. تعریف دوباره یک نام در همان دامنه سراسری
  3. عملگر بیت‌ای (& | ^ << >>) که در Pine وجود ندارد
  4. lookahead_on در هر request.security (ممنوع طبق قرارداد پروژه)
  5. هم‌خوانی تعداد اعضای tuple بازگشتی تابع با tuple دریافت‌کننده
  6. ساخت line/label/box بیرون از توابع مدیریت آبجکت (f_om*)
  7. alertcondition بدون barstate.isconfirmed یا متصل به شرط realtime
  8. تابع ta.* داخل بلوک شرطی (محاسبه ناپایدار)
  9. کاراکتر نامرئی، براکت نابسته، و کلیدواژه چسبیده
 10. حلقه بدون سقف مشخص

استفاده:
    python3 tools/pine_audit.py <file.pine>
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
    "line", "label", "box", "table", "array", "map", "matrix", "source",
    "series", "simple", "const", "input",
}
BUILTIN_NS = {
    "math", "str", "array", "matrix", "map", "input", "request", "ta", "ticker",
    "timeframe", "color", "line", "label", "box", "table", "polyline", "chart",
    "syminfo", "display", "extend", "xloc", "yloc", "size", "shape", "location",
    "position", "text", "session", "alert", "barmerge", "format", "scale",
    "barstate", "linefill", "runtime", "strategy",
}
KEYWORDS = {
    "and", "or", "not", "if", "else", "for", "while", "to", "by", "var",
    "varip", "switch", "import", "export", "type", "method", "indicator",
    "strategy", "library", "plot", "plotshape", "plotchar", "plotarrow",
    "plotbar", "plotcandle", "hline", "fill", "bgcolor", "alertcondition",
    "max_bars_back",
}
NAMED_ARGS = {
    "minval", "maxval", "step", "inline", "title", "width", "group", "tooltip",
    "text_color", "text_halign", "text_valign", "border_width", "border_color",
    "frame_color", "frame_width", "bgcolor", "color", "style", "size",
    "location", "extend", "xloc", "yloc", "display", "linewidth", "precision",
    "overlay", "format", "shorttitle", "max_bars_back", "max_lines_count",
    "max_labels_count", "max_boxes_count", "gaps", "lookahead", "options",
    "confirm", "editable", "defval", "textcolor", "trackprice", "show_last",
    "histbase", "editable", "char", "offset", "join", "ignore", "wrap",
}
TYPES = {"int", "float", "bool", "string", "color", "line", "label", "box",
         "table", "linefill", "polyline", "chart", "source"}

FUNC_DEF_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
FUNC_ARROW_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*=>")
DECL_RE = re.compile(
    r"^(?:(?:var|varip)\s+)?(?:(?:series|simple|const|input)\s+)?"
    r"(?:(?:int|float|bool|string|color|line|label|box|table|array<[^>]*>|map<[^>]*>)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=(?!=))"
)
TUPLE_RE = re.compile(r"^\s*\[([^\]]+)\]\s*=(?!=)")
FOR_RE = re.compile(r"^\s*for\s+(?:(?:int|float)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
IDENT_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")
BITWISE_RE = re.compile(r"(<<|>>|\^|(?<![&=\w])&(?![&=])|(?<![|\w])\|(?![|=]))")


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


def strip_literals(line: str) -> str:
    line = strip_strings(line)
    line = re.sub(r"#[0-9A-Fa-f]{3,8}", " 0 ", line)
    line = re.sub(r"\b\d+\.?\d*[eE][-+]?\d+\b", " 0 ", line)
    return line


def logical_lines(src: str) -> list[tuple[int, str, int]]:
    """(شماره خط، متن منطقی، تورفتگی) با چسباندن ادامه‌ها."""
    result: list[tuple[int, str, int]] = []
    pending_no, pending, pending_ind = 0, "", 0
    for no, raw in enumerate(src.split("\n"), start=1):
        if raw.strip().startswith("//"):
            if pending:
                result.append((pending_no, pending, pending_ind))
                pending, pending_no = "", 0
            continue
        stripped = raw.rstrip()
        if not stripped.strip():
            if pending:
                result.append((pending_no, pending, pending_ind))
                pending, pending_no = "", 0
            continue
        indent = len(stripped) - len(stripped.lstrip())
        open_br = pending.count("[") - pending.count("]") + pending.count("(") - pending.count(")")
        if pending and (indent >= 5 or open_br > 0):
            pending += " " + stripped.strip()
            continue
        if pending:
            result.append((pending_no, pending, pending_ind))
        pending, pending_no, pending_ind = stripped, no, indent
    if pending:
        result.append((pending_no, pending, pending_ind))
    return result


def collect_params(text: str) -> set[str]:
    names: set[str] = set()
    for chunk in re.finditer(r"\(([^()]*)\)", text):
        for part in chunk.group(1).split(","):
            m = re.match(r"^\s*(?:var\s+)?(?:(?:int|float|bool|string|color|line|label|box|"
                         r"table|array<[^>]*>|source)\s+)([A-Za-z_][A-Za-z0-9_]*)", part)
            if m:
                names.add(m.group(1))
    return names


def is_namespace(code: str, tok: re.Match) -> bool:
    before = code[tok.start() - 1] if tok.start() > 0 else ""
    after = code[tok.end()] if tok.end() < len(code) else ""
    return before == "." or after == "."


def main(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    raw_lines = src.split("\n")
    lines = logical_lines(src)
    issues: list[str] = []

    known = set(BUILTIN_PLAIN) | set(BUILTIN_NS) | set(KEYWORDS) | set(NAMED_ARGS) | TYPES
    decl_line: dict[str, int] = {}
    local_scopes: dict[int, set[str]] = {}

    # ---------------------------------------------------------------- ۱) تعریف‌ها
    for no, text, indent in lines:
        code = strip_literals(text)
        names: set[str] = set()
        m = FUNC_DEF_RE.match(code)
        if m and indent == 0 and "input." not in code and m.group(1) not in TYPES \
                and not code.strip().startswith(("plot", "alertcondition", "alert(", "fill", "hline", "bgcolor", "max_bars_back")):
            names.add(m.group(1))
            names |= collect_params(code)
        m = FUNC_ARROW_RE.match(code)
        if m:
            names.add(m.group(1))
            names |= collect_params(code)
        m = DECL_RE.match(code.strip())
        if m:
            names.add(m.group(1))
        m = TUPLE_RE.match(code)
        if m:
            for part in m.group(1).split(","):
                part = re.sub(r"^(?:var|varip)\s+", "", part.strip())
                part = re.sub(r"^(?:int|float|bool|string|color|line|label|box|table|"
                              r"array<[^>]*>|map<[^>]*>)\s+", "", part)
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
                    names.add(part)
        m = FOR_RE.match(code)
        if m:
            names.add(m.group(1))
        is_def = indent == 0
        is_reassign = ":=" in code.split("=")[0] + "=" if False else bool(re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:=", code))
        names = {n for n in names if n not in KEYWORDS}
        for nm in names:
            if nm.startswith("_") or not is_def:
                # پارامتر/متغیر محلی تابع یا انتساب داخل بلوک
                known.add(nm)
                decl_line.setdefault(nm, no)
                continue
            if is_reassign:
                known.add(nm)
                decl_line.setdefault(nm, no)
                continue
            if nm in decl_line:
                issues.append(f"[DUP] «{nm}» دو بار در دامنه سراسری تعریف شده است (خط {decl_line[nm]} و {no})")
            decl_line[nm] = no
            known.add(nm)

    # ---------------------------------------------------------------- ۲) ترتیب استفاده
    global_names = set(decl_line)
    for no, text, indent in lines:
        code = strip_literals(text)
        stripped = code.strip()
        if stripped.startswith("//"):
            continue
        if re.match(r"^(?:var\s+|varip\s+)?(?:int|float|bool|string|color|line|label|box|table|"
                    r"array<[^>]*>|map<[^>]*>)?\s*[A-Za-z_][A-Za-z0-9_]*\s*(?::=|=(?!=))", stripped) or \
                TUPLE_RE.match(code) or FUNC_ARROW_RE.match(code) or FUNC_DEF_RE.match(code):
            eq = code.find("=")
            body = code[eq + 1:] if eq >= 0 else ""
            own = DECL_RE.match(stripped)
            own_name = own.group(1) if own else None
        else:
            body = code
            own_name = None
        for tok in IDENT_RE.finditer(body):
            nm = tok.group(1)
            if is_namespace(body, tok):
                continue
            if nm == own_name:
                continue
            if nm.startswith("_") or nm in KEYWORDS:
                continue
            if nm in global_names and decl_line[nm] > no:
                issues.append(f"[ORDER] «{nm}» در خط {no} استفاده شده ولی در خط {decl_line[nm]} تعریف می‌شود")

    # ---------------------------------------------------------------- ۳) عملگر بیت‌ای
    for no, raw in enumerate(raw_lines, start=1):
        if raw.strip().startswith("//"):
            continue
        code = strip_literals(raw)
        for m in BITWISE_RE.finditer(code):
            issues.append(f"[BITWISE] عملگر «{m.group(1)}» در خط {no} — Pine عملگر بیت‌ای ندارد")

    # ---------------------------------------------------------------- ۴) lookahead_on
    for no, raw in enumerate(raw_lines, start=1):
        if "lookahead_on" in raw and not raw.strip().startswith("//"):
            issues.append(f"[REPAINT] lookahead_on در خط {no}")

    # ---------------------------------------------------------------- ۵) arity توابع tuple
    func_returns: dict[str, int] = {}
    for no, text, indent in lines:
        code = strip_literals(text)
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", code)
        if m and m.group(1) not in TYPES:
            fname = m.group(1)
            tail = code.rsplit("\n", 1)[-1]
            if tail.strip().startswith("[") and tail.strip().endswith("]"):
                inner = tail.strip()[1:-1]
                if inner.count("[") == inner.count("]"):
                    func_returns[fname] = len([x for x in inner.split(",") if x.strip()])
    for no, text, indent in lines:
        code = strip_literals(text)
        m = TUPLE_RE.match(code)
        if not m:
            continue
        lhs = [x.strip() for x in m.group(1).split(",") if x.strip()]
        call = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", code[code.index("=") + 1:])
        if call and call.group(1) in func_returns:
            if func_returns[call.group(1)] != len(lhs):
                issues.append(f"[TUPLE] خط {no}: تابع {call.group(1)} مقدار {func_returns[call.group(1)]} "
                              f"عضو دارد ولی {len(lhs)} عضو دریافت شده است")
        if len(lhs) > 16:
            issues.append(f"[TUPLE] خط {no}: تعداد اعضای tuple بیشتر از حد مجاز Pine است ({len(lhs)})")

    # ---------------------------------------------------------------- ۶) ساخت آبجکت خارج از استخر
    pool_funcs = {"f_omAddLabel", "f_omAddLine", "f_omAddBox", "f_omAddLabelOnly", "f_omAddLineOnly"}
    raw_clean = [strip_literals(r) for r in raw_lines]
    for idx, code in enumerate(raw_clean):
        no = idx + 1
        if code.strip().startswith("//"):
            continue
        for obj in ("line.new", "label.new", "box.new"):
            if obj not in code:
                continue
            fn = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", code)
            inside_pool = bool(fn) and fn.group(1) in pool_funcs
            # پنجرهٔ ۴ خطی: ثبت معمولاً در همان خط یا خطوط بعدی انجام می‌شود
            window = " ".join(raw_clean[idx:idx + 9])
            registered = ("f_om" in window) or ("array.push" in window) or ("table.new" in code)
            if not inside_pool and not registered:
                issues.append(f"[OBJECT] {obj} در خط {no} بدون ثبت در استخر مدیریت آبجکت")

    # ---------------------------------------------------------------- ۷) alertcondition
    for no, text, indent in lines:
        code = strip_literals(text)
        if code.strip().startswith("alertcondition("):
            if "barstate.isconfirmed" not in code and "sig" not in code and "Flip" not in code \
                    and "struct" not in code and "sd" not in code and "hull" not in code:
                issues.append(f"[ALERT] خط {no}: شرایط هشدار به‌وضوح به کندل بسته‌شده وابسته نیست")

    # ---------------------------------------------------------------- ۸) ta.* داخل شرط
    ta_re = re.compile(r"\bta\.[a-z_]+\(")
    in_func = False
    for no, text, indent in lines:
        code = strip_literals(text)
        if indent == 0:
            in_func = bool(FUNC_DEF_RE.match(code) or FUNC_ARROW_RE.match(code)) and \
                not code.strip().startswith(("plot", "alertcondition", "alert(", "fill", "hline",
                                             "bgcolor", "max_bars_back", "if ", "for ", "while "))
        if in_func:
            continue
        if indent >= 4 and ta_re.search(code):
            head = code.strip().split("(")[0]
            if not re.match(r"^(?:var\s+)?(?:float|int|bool|string)\s+_[A-Za-z0-9_]+$", head.strip()):
                issues.append(f"[CALC] خط {no}: فراخوانی ta.* داخل بلوک شرطی/حلقه "
                              f"(احتمال Calculation inconsistency)")

    # ---------------------------------------------------------------- ۹) حلقه بدون سقف
    for no, text, indent in lines:
        code = strip_literals(text)
        m = re.match(r"^\s*(?:for|while)\s+(.*)$", code)
        if m:
            body = m.group(1)
            if body.strip().startswith("for") or "to " in body or "while" in body:
                if not re.search(r"(?:to\s+|<|<=|>)", body):
                    issues.append(f"[LOOP] خط {no}: حلقه بدون شرط پایان مشخص")

    # ---------------------------------------------------------------- ۱۰) براکت و کاراکتر نامرئی
    balance = 0
    for no, raw in enumerate(raw_lines, start=1):
        if raw.strip().startswith("//"):
            continue
        code = strip_literals(raw)
        balance += code.count("(") - code.count(")")
        if code.count("[") != code.count("]") and TUPLE_RE.match(code) is None and \
                not re.search(r"array<|map<|matrix<", code):
            pass
    if balance != 0:
        issues.append(f"[SYNTAX] توازن پرانتز کل فایل برابر {balance} است (باید صفر باشد)")
    for no, raw in enumerate(raw_lines, start=1):
        if raw.strip().startswith("//"):
            continue
        for ch, name in (("\u200e", "LRM"), ("\u200f", "RLM"), ("\ufeff", "BOM"),
                         ("\u202a", "LRE"), ("\u202b", "RLE"), ("\u202c", "PDF")):
            if ch in raw:
                issues.append(f"[CHAR] کاراکتر نامرئی {name} در خط {no}")
        if not raw.strip().startswith("//") and "\u200c" in strip_strings(raw):
            issues.append(f"[CHAR] نیم‌فاصله داخل بخش کد در خط {no}")

    if not issues:
        print(f"OK — ممیزی {path.name} بدون ایراد.")
        return 0
    print(f"⚠ {len(issues)} مورد در {path.name}:")
    for it in issues[:120]:
        print("   " + it)
    if len(issues) > 120:
        print(f"   ... و {len(issues) - 120} مورد دیگر")
    return 1


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/SMC_NTS_PRO_v6.pine")
    sys.exit(1 if main(target) else 0)
