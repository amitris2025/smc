#!/usr/bin/env python3
"""
check_pine.py — یک بررسی‌کننده سبک (linter) برای قطعات Pine Script v5.

کاری که انجام می‌دهد (بدون نیاز به کامپایلر رسمی تریدینگ‌ویو):
  1. یافتن کاراکترهای نامرئی مخرب (ZWNJ / ZWJ / BOM / RLM / LRM)
     که هنگام کپی از پیام‌رسان‌ها وارد کد می‌شوند و باعث خطای کامپایل می‌گردند.
  2. بررسی توازن پرانتز / کروشه / آکولاد (با نادیده گرفتن کامنت و رشته‌ها)
  3. یافتن کلیدواژه‌های چسبیده (orinRevSellZone ، -1and ، x)and و ...)
  4. یافتن بازنویسی متغیرهای ورودی (input.*) با :=  — که در Pine مجاز نیست
  5. یافتن := روی متغیرهای تعریف‌نشده در محدوده بررسی

نحوه استفاده:
    python3 tools/check_pine.py <file.pine> [<file2.pine> ...]
    python3 tools/check_pine.py modules/          # کل پوشه، به ترتیب نام فایل
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INVISIBLE = {
    "\u200c": "ZWNJ (نیم‌فاصله)",
    "\u200d": "ZWJ",
    "\u200e": "LRM",
    "\u200f": "RLM",
    "\ufeff": "BOM",
    "\u00a0": "nbsp",
    "\u202a": "LRE",
    "\u202b": "RLE",
    "\u202c": "PDF",
}

PAIRS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {")", "]", "}"}

# شناسه‌های مجاز که با and/or/not شروع می‌شوند (مثل color.orange)
SAFE_PREFIX_WORDS = {"orange", "orangered", "order", "orders", "orderid", "notif"}

# کلمه‌های کاملی که «and/or/not» بخشی از خودِ نام هستند (نه کلیدواژه چسبیده).
SAFE_WHOLE_WORDS = {
    "color", "_color", "border_color", "text_color", "frame_color", "bgcolor",
    "orange", "order", "android", "notify", "notation", "normal", "normalize",
    "north", "notch", "note", "annotation", "core", "correlation", "floor",
    "floor_or", "for", "format", "formula", "important", "report", "support",
}

# کلیدواژه‌های چسبیده به شناسه/عدد
GLUE_PATTERNS = [
    (re.compile(r"(?<![A-Za-z0-9_._])(and|or|not)(?=[A-Za-z_\u0600-\u06ff])"),
     "کلیدواژه چسبیده به شناسه بعدی (فاصله قبل از and/or/not لازم است)"),
    (re.compile(r"[0-9](?:and|or|not)\b"),
     "کلیدواژه چسبیده به عدد قبلی (مثل -1and)"),
    (re.compile(r"\)(?:and|or|not)\b"),
     "کلیدواژه چسبیده به پرانتز بسته"),
]

INPUT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*input\.")
REASSIGN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:=")
DECLARE_RE = re.compile(
    r"(?:^|\n)\s*(?:(?:var|varip)\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)"
)


def strip_comments_and_strings(src: str) -> tuple[str, list[bool]]:
    """حذف کامنت‌های // و /* */ و رشته‌ها.

    خروجی: (متن پاک‌شده با حفظ تعداد خط‌ها، ماسک «آیا این کاراکتر کد است؟»)
    کاراکترهای نامرئی داخل کامنت/رشته برای Pine بی‌خطرند، ولی نیم‌فاصله در
    متن فارسیِ کامنت کاملاً طبیعی است — پس فقط بخش کد بررسی می‌شود.
    """
    out: list[str] = []
    is_code: list[bool] = []
    i, n = 0, len(src)
    in_str = None
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if in_str:
            if ch == "\\":
                out.append("  ")
                is_code += [False, False]
                i += 2
                continue
            if ch == in_str:
                in_str = None
            out.append("\n" if ch == "\n" else " ")
            is_code.append(False)
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            out.append(" ")
            is_code.append(False)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                is_code.append(False)
                i += 1
            continue
        if ch == "/" and nxt == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                is_code.append(False)
                i += 1
            for _ in range(2):
                if i < n:
                    out.append(" ")
                    is_code.append(False)
                    i += 1
            continue
        out.append(ch)
        is_code.append(True)
        i += 1
    return "".join(out), is_code


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check_invisible(raw: str, code_mask: list[bool], label: str,
                    problems: list[str]) -> None:
    """فقط کاراکترهای نامرئیِ «بخش کد» گزارش می‌شوند"""
    for ch, name in INVISIBLE.items():
        hits = [i for i, c in enumerate(raw[:len(code_mask)]) if c == ch and code_mask[i]]
        if hits:
            ln = line_of(raw, hits[0])
            problems.append(
                f"[{label}:{ln}] کاراکتر نامرئی {name} (U+{ord(ch):04X}) داخل کد یافت شد "
                f"({len(hits)} مورد) — باید حذف شود"
            )


def check_balance(clean: str, label: str, problems: list[str]) -> None:
    stack: list[tuple[str, int]] = []   # ( opener , line )
    for i, ch in enumerate(clean):
        if ch in PAIRS:
            stack.append((ch, line_of(clean, i)))
        elif ch in CLOSERS:
            if not stack:
                problems.append(f"[{label}:{line_of(clean, i)}] بسته‌شدن اضافی '{ch}'")
                return
            op, ln = stack.pop()
            if PAIRS[op] != ch:
                problems.append(
                    f"[{label}:{line_of(clean, i)}] ناهماهنگی: '{op}' باز شده در خط {ln} "
                    f"اما با '{ch}' بسته شده"
                )
                return
    for op, ln in stack:
        problems.append(f"[{label}:{ln}] '{op}' باز مانده و بسته نشده است")


def check_glue(clean: str, label: str, problems: list[str]) -> None:
    for pat, msg in GLUE_PATTERNS:
        for m in pat.finditer(clean):
            # کلمه کاملی که در این محل شروع می‌شود (برای عبور از color.orange و مانند آن)
            word = re.match(r"[A-Za-z_][A-Za-z0-9_]*", clean[m.start():])
            if word and word.group(0).lower() in SAFE_PREFIX_WORDS:
                continue
            ln = line_of(clean, m.start())
            problems.append(f"[{label}:{ln}] {msg}: «{m.group(0)}»")


def check_swallowed_keyword(clean: str, declared: set[str], label: str,
                            problems: list[str]) -> None:
    """یافتن شناسه‌هایی که کلیدواژه بعد از خود را بلعیده‌اند.

    نمونه‌های واقعیِ رخ‌داده:
        bearishConfirmationand  → bearishConfirmation + and
        kdSellSignaland         → kdSellSignal + and
    بررسی فقط روی نام‌هایی انجام می‌شود که در همین محدوده تعریف شده باشند،
    تا خطای مثبتِ کاذب (false positive) نداشته باشیم.
    """
    pat = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*?)(and|or|not)\b")
    for m in pat.finditer(clean):
        name = m.group(1)
        whole = m.group(0)
        if len(name) < 3 or name in {"and", "or", "not"}:
            continue
        if name.lower() in SAFE_PREFIX_WORDS:
            continue
        # اگر خودِ کلمهٔ کامل یک شناسهٔ معتبر باشد (مثل _color یا border_color)
        # این یک کلیدواژهٔ چسبیده نیست، بلکه بخشی از یک نام است.
        if whole in declared or whole.lower() in SAFE_WHOLE_WORDS:
            continue
        if name in declared:
            ln = line_of(clean, m.start())
            problems.append(
                f"[{label}:{ln}] «{m.group(0)}» احتمالاً «{name} {m.group(2)}» است "
                f"(فاصله جا افتاده)"
            )


def collect_declarations(clean: str) -> set[str]:
    declared = set(DECLARE_RE.findall(clean))
    # var/varip اعلان‌ها
    declared |= set(re.findall(r"\b(?:var|varip)\s+([A-Za-z_][A-Za-z0-9_]*)", clean))
    # اعلان‌های نوع‌دار (v5/v6): int x = ..., float y = ...
    declared |= set(
        re.findall(r"\b(?:int|float|bool|string|color|line|label|table|box)\s+"
                   r"([A-Za-z_][A-Za-z0-9_]*)\s*=", clean)
    )
    # پارامترهای تابع
    declared |= set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=>", clean))
    return declared


def check_inputs_and_decls(clean: str, declared: set[str], label: str,
                           problems: list[str]) -> None:
    inputs = set(INPUT_RE.findall(clean))

    seen: set[str] = set()
    for m in REASSIGN_RE.finditer(clean):
        name = m.group(1)
        if name in seen:
            continue
        if name in inputs:
            ln = line_of(clean, m.start())
            problems.append(
                f"[{label}:{ln}] بازنویسی ورودی '{name}' با := مجاز نیست "
                f"(از یک متغیر مؤثر مثل {name}Eff استفاده کنید)"
            )
        seen.add(name)

    for m in REASSIGN_RE.finditer(clean):
        name = m.group(1)
        if name not in declared and name not in inputs:
            ln = line_of(clean, m.start())
            problems.append(
                f"[{label}:{ln}] '{name}' با := مقدار می‌گیرد ولی در این محدوده "
                f"با = تعریف نشده است (احتمالاً باید در ماژول قبل تعریف شود)"
            )
            seen.add(name)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    targets: list[Path] = []
    for arg in argv[1:]:
        p = Path(arg)
        if p.is_dir():
            targets += sorted(
                f for f in p.rglob("*")
                if f.suffix in {".pine", ".pinescript", ".txt"}
            )
        elif p.is_file():
            targets.append(p)
        else:
            print(f"! مسیر یافت نشد: {arg}")
            return 2

    if not targets:
        print("! فایلی برای بررسی پیدا نشد")
        return 2

    total = 0
    # الف) بررسی نامرئی‌ها به‌صورت هر فایل جداگانه
    for f in targets:
        raw = f.read_text(encoding="utf-8", errors="replace")
        _, mask = strip_comments_and_strings(raw)
        probs: list[str] = []
        check_invisible(raw, mask, f.name, probs)
        if probs:
            print(f"\n--- {f.name} ---")
            for p in probs:
                print("  ", p)
            total += len(probs)

    # ب) بررسی نحوی روی کل مجموعه (یک محدوده واحد، به ترتیب نام فایل)
    combined = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in targets)
    clean, _ = strip_comments_and_strings(combined)
    label = "ALL"
    probs = []
    declared = collect_declarations(clean)
    check_balance(clean, label, probs)
    check_glue(clean, label, probs)
    check_swallowed_keyword(clean, declared, label, probs)
    check_inputs_and_decls(clean, declared, label, probs)
    if probs:
        print(f"\n--- بررسی سراسری ({len(targets)} فایل) ---")
        for p in probs:
            print("  ", p)
        total += len(probs)

    if total == 0:
        print(f"OK — {len(targets)} فایل بررسی شد، مشکلی یافت نشد.")
        return 0
    print(f"\n{total} مورد نیاز به توجه.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
