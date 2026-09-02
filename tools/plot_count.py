#!/usr/bin/env python3
"""
شمارش plot count طبق قوانین مستندات TradingView:
  https://www.tradingview.com/pine-script-docs/writing/limitations/
توابعی که سهم مصرف می‌کنند:
  plot() plotarrow() plotbar() plotcandle() plotchar() plotshape()
  alertcondition() bgcolor() barcolor() و fill() (فقط اگر رنگش series باشد)
هر آرگومان رنگیِ series (color/textcolor/wickcolor/bordercolor) یک سهم اضافه
می‌کند. رنگ const (color.white) یا input (color.new(colBuy, 45) که colBuy یک
input.color است) سهم اضافه نمی‌کند.
"""
import re, sys

FUNCS = ('plot', 'plotarrow', 'plotbar', 'plotcandle', 'plotchar', 'plotshape',
         'alertcondition', 'bgcolor', 'barcolor', 'fill')
COLOR_KEYS = ('color', 'textcolor', 'wickcolor', 'bordercolor')
CONST_COLORS = {'red','green','blue','white','black','orange','yellow','gray','grey','lime',
                'maroon','navy','olive','purple','silver','teal','aqua','fuchsia'}

def strip_comments(src):
    out = []
    for ln in src.split('\n'):
        # حذف کامنت (با احترام به رشته‌ها)
        res = ''
        in_str = False
        i = 0
        while i < len(ln):
            c = ln[i]
            if c == '"' and (i == 0 or ln[i-1] != '\\'):
                in_str = not in_str
            if not in_str and c == '/' and i + 1 < len(ln) and ln[i+1] == '/':
                break
            res += c
            i += 1
        out.append(res)
    return '\n'.join(out)

def collect_inputs(src):
    """نام ورودی‌های input.color — رنگِ input، series محسوب نمی‌شود."""
    return set(re.findall(r'^\s*(\w+)\s*=\s*input\.color\(', src, re.M))

def split_args(argstr):
    args, depth, cur, in_str = [], 0, '', False
    for ch in argstr:
        if ch == '"' :
            in_str = not in_str
        if not in_str:
            if ch in '([': depth += 1
            elif ch in ')]': depth -= 1
            elif ch == ',' and depth == 0:
                args.append(cur); cur = ''; continue
        cur += ch
    if cur.strip(): args.append(cur)
    return args

def extract_value(argstr, key):
    """مقدار یک آرگومان نام‌دار با در نظر گرفتن کمان‌های تودرتو."""
    m = re.search(r'(?<![\w.])' + key + r'\s*=\s*', argstr)
    if not m:
        return None
    i, depth, in_str, out = m.end(), 0, False, ''
    while i < len(argstr):
        c = argstr[i]
        if c == '"':
            in_str = not in_str
        if not in_str:
            if c in '([':
                depth += 1
            elif c in ')]':
                if depth == 0:
                    break
                depth -= 1
            elif c == ',' and depth == 0:
                break
        out += c
        i += 1
    return out.strip()

def is_series_color(expr, color_inputs):
    e = expr.strip()
    if not e: return False
    if re.fullmatch(r'color\.\w+', e):                      # color.white
        return e.split('.')[1] not in CONST_COLORS or False
    m = re.fullmatch(r'color\.new\(([^,]+),[^)]*\)', e)     # color.new(X, n)
    if m:
        inner = m.group(1).strip()
        return is_series_color(inner, color_inputs)
    if re.fullmatch(r'\w+', e):
        return e not in color_inputs and e not in CONST_COLORS
    return True                                             # عبارت شرطی = series

def find_calls(src):
    calls = []
    for fn in FUNCS:
        for m in re.finditer(r'(?<![\w.])' + fn + r'\s*\(', src):
            start = m.end() - 1
            depth, i, in_str = 0, start, False
            while i < len(src):
                c = src[i]
                if c == '"': in_str = not in_str
                if not in_str:
                    if c == '(': depth += 1
                    elif c == ')':
                        depth -= 1
                        if depth == 0: break
                i += 1
            calls.append((fn, src[start+1:i], src[:m.start()].count('\n') + 1))
    return calls

def main(path):
    raw = open(path, encoding='utf-8').read()
    src = strip_comments(raw)
    color_inputs = collect_inputs(raw)
    total, rows = 0, []
    for fn, args, line in sorted(find_calls(src), key=lambda x: x[2]):
        n = 0
        extra = []
        if fn == 'fill':
            val = extract_value(args, 'color')
            if val and is_series_color(val, color_inputs):
                n = 1; extra.append('series color')
        else:
            n = 1
            for key in COLOR_KEYS:
                if fn == 'alertcondition':
                    continue
                val = extract_value(args, key)
                if val and is_series_color(val, color_inputs):
                    n += 1; extra.append(key)
        total += n
        rows.append((line, fn, n, ','.join(extra), args.strip().split(',')[0][:48]))
    for r in rows:
        print(f'{r[0]:>5}  {r[1]:<15} +{r[2]}  {r[4]}{"  ["+r[3]+"]" if r[3] else ""}')
    print(f'\n>>> مجموع plot count = {total}   (سقف مجاز = 64)')
    if total > 64:
        print('خطا: از سقف ۶۴ عبور کرده‌اید — TradingView کامپایل نمی‌کند.')
        return 1
    print(f'>>> حاشیه امن باقی‌مانده = {64 - total}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'src/SMC_NTS_PRO_v6.pine'))
