#!/usr/bin/env python3
"""بررسی بودجهٔ plot count اسکریپت‌های Pine (سقف ۶۴ تایی TradingView، خطای RE10140).

TradingView برای هر اسکریپت حداکثر ۶۴ plot count مجاز می‌کند. تولیدکننده‌ها:
plot/plotshape/plotchar/plotarrow/plotbar/plotcandle (۱ تا ۷ واحد بسته به آرگومان‌های
سری)، alertcondition/bgcolor/barcolor (۱ واحد) و fill فقط وقتی رنگش series باشد (۱ واحد).
hline/line.new/label.new/box.new/table.new واحد مصرف نمی‌کنند.

نکته: هر آرگومان رنگی که از یک متغیر/ترنری series بیاید یک واحد اضافه می‌گیرد؛
رنگ ثابت (color.red یا color.new(color.red, 50)) واحد اضافه نمی‌گیرد.

استفاده:
    python3 tools/check_plot_budget.py src/SMC_NTS_Pro.pine [file ...]
"""
import re
import sys

LIMIT = 64
PLOT_FNS = ("plot", "plotshape", "plotchar", "plotarrow", "plotbar", "plotcandle")
ONE_UNIT_FNS = ("alertcondition", "bgcolor", "barcolor")


def strip_noise(src: str) -> str:
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r'"(?:[^"]|\\")*"', "''", src)  # رشته‌ها (مثل {{plot("X")}}) خالی شوند
    return src


def split_calls(s: str, name: str):
    """بدنهٔ هر فراخوانی name( ... ) را با توازن پرانتز استخراج می‌کند."""
    out = []
    for m in re.finditer(r"\b" + name + r"\s*\(", s):
        depth = 0
        for j in range(m.end() - 1, len(s)):
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
                if depth == 0:
                    out.append(s[m.end():j])
                    break
    return out


def top_args(body: str):
    args, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(body[start:i])
            start = i + 1
    args.append(body[start:])
    return args


def get_arg(body: str, key: str):
    for a in top_args(body):
        m = re.match(key + r"\s*=\s*(.+)$", a.strip(), re.S)
        if m:
            return m.group(1).strip()
    return None


def color_is_series(val) -> bool:
    """رنگ ثابت است یا series؟ (طبق مثال رسمی مستندات Limitations)."""
    if val is None:
        return False
    v = val.strip()
    if v == "na" or re.fullmatch(r"color\.\w+", v):
        return False
    m = re.fullmatch(r"color\.new\s*\((.*)\)", v, re.S)
    if m:
        inner = top_args(m.group(1))
        base_ok = len(inner) >= 1 and re.fullmatch(r"\s*color\.\w+\s*", inner[0]) is not None
        transp_ok = len(inner) >= 2 and re.fullmatch(r"\s*\d+\s*", inner[1]) is not None
        return not (base_ok and transp_ok)
    return True  # متغیر، ترنری یا عبارت → series


def count_file(path: str) -> int:
    raw = open(path, encoding="utf-8").read()
    s = strip_noise(raw)
    total = 0
    for body in split_calls(s, "plot"):
        total += 1 + (1 if color_is_series(get_arg(body, "color")) else 0)
    for body in split_calls(s, "plotshape"):
        total += 1
        total += 1 if color_is_series(get_arg(body, "color")) else 0
        total += 1 if color_is_series(get_arg(body, "textcolor")) else 0
    for body in split_calls(s, "plotchar"):
        total += 1
        total += 1 if color_is_series(get_arg(body, "color")) else 0
        total += 1 if color_is_series(get_arg(body, "textcolor")) else 0
    for fn in ("plotarrow",):
        for body in split_calls(s, fn):
            total += 1
            for k in ("colorup", "colordown"):
                total += 1 if color_is_series(get_arg(body, k)) else 0
    for fn in ("plotbar", "plotcandle"):
        for body in split_calls(s, fn):
            # open/high/low/close = 4 واحد پایه
            total += 4
            total += 1 if color_is_series(get_arg(body, "color")) else 0
            if fn == "plotcandle":
                total += 1 if color_is_series(get_arg(body, "wickcolor")) else 0
                total += 1 if color_is_series(get_arg(body, "bordercolor")) else 0
    for body in split_calls(s, "fill"):
        total += 1 if color_is_series(get_arg(body, "color")) else 0
    for fn in ONE_UNIT_FNS:
        total += len(split_calls(s, fn))
    return total


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print("usage: check_plot_budget.py <file.pine> [file ...]")
        return 2
    worst = 0
    ok = True
    for p in paths:
        n = count_file(p)
        worst = max(worst, n)
        status = "OK" if n <= LIMIT else "OVER"
        if n > LIMIT:
            ok = False
        print(f"{p}: plot count = {n} / {LIMIT}  [{status}]"
              + ("" if n <= LIMIT else f"  → {n - LIMIT} واحد اضافه"))
    print("-" * 56)
    print("حداکثر: " + str(worst) + f"/{LIMIT} — " + ("مجاز ✔" if ok else "خطای RE10140 ✘"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
