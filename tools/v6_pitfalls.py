#!/usr/bin/env python3
# =============================================================================
#  v6_pitfalls.py — بررسی قواعد ناسازگار Pine v6 (از راهنمای مهاجرت رسمی)
# =============================================================================
#  A) bool دیگر نمی‌تواند na باشد؛ na()/nz()/fixnan() آرگومان bool نمی‌پذیرند
#  B) int و float دیگر به‌صورت ضمنی به bool تبدیل نمی‌شوند (شرط if/while/?:)
#  C) یک فراخوانی نمی‌تواند برای یک پارامتر بیش از یک آرگومان داشته باشد
#  D) مقدار timeframe باید multiplier داشته باشد ("1D" نه "D")
#  E) طول توابع ta.* باید simple/const/input باشد (متغیر mutable نه)
#  F) پارامتر offset مقدار series نمی‌پذیرد
# =============================================================================
import re
import sys

BOOL_DECL = re.compile(r'^\s*(?:var\s+|varip\s+)?bool\s+(\w+)\s*=\s*(.+)$')
BOOL_ASSIGN = re.compile(r'^\s*(\w+)\s*:=\s*(.+)$')
COND = re.compile(r'^\s*(?:if|while)\s+(.+?)\s*$')
NA_CALL = re.compile(r'\b(na|nz|fixnan)\s*\(')
SEC = re.compile(r'request\.\w+\s*\([^,]+,\s*"([A-Za-z]+)"')
TA = re.compile(r'\bta\.(\w+)\s*\(')
OFFSET = re.compile(r'\boffset\s*=\s*([^,)]+)')


def strip_comment(line):
    out, in_str, i = '', False, 0
    while i < len(line):
        c = line[i]
        if c == '"' and (i == 0 or line[i - 1] != '\\'):
            in_str = not in_str
        if not in_str and c == '/' and line[i:i + 2] == '//':
            break
        out += c
        i += 1
    return out


def logical_lines(lines):
    """جملات منطقی (چندخطی‌ها با هم) به‌همراه شمارهٔ خط شروع."""
    out, cur, start, depth = [], '', 0, 0
    for i, raw in enumerate(lines, 1):
        code = strip_comment(raw)
        if not code.strip():
            continue
        if not cur:
            start = i
        cur += (' ' if cur else '') + code.strip()
        depth += code.count('(') + code.count('[') - code.count(')') - code.count(']')
        nxt_is_cont = depth > 0
        if not nxt_is_cont:
            out.append((start, cur))
            cur, depth = '', 0
    if cur:
        out.append((start, cur))
    return out


def named_args(call_text):
    args, depth, cur, in_str = [], 0, '', False
    for ch in call_text:
        if ch == '"':
            in_str = not in_str
        if not in_str:
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            elif ch == ',' and depth == 0:
                args.append(cur)
                cur = ''
                continue
        cur += ch
    if cur.strip():
        args.append(cur)
    names = []
    for a in args:
        m = re.match(r'^\s*(\w+)\s*=(?!=)', a)
        if m:
            names.append(m.group(1))
    return names


def check(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    stmts = logical_lines(lines)
    errs = []
    bool_vars = set()
    numeric_vars = set()
    mutable = set()          # متغیرهایی که با := تغییر می‌کنند
    inputs = set()

    for ln, s in stmts:
        mi = re.match(r'^\s*(\w+)\s*=\s*input\.\w+\(', s)
        if mi:
            inputs.add(mi.group(1))
        mb = BOOL_DECL.match(s)
        if mb:
            bool_vars.add(mb.group(1))
            if re.match(r'^\s*na\s*$', mb.group(2).strip()):
                errs.append((ln, 'A', 'bool ' + mb.group(1),
                             'متغیر bool نمی‌تواند مقدار na بگیرد (v6)'))
        mn = re.match(r'^\s*(?:var\s+|varip\s+)?(int|float)\s+(\w+)\s*=', s)
        if mn:
            numeric_vars.add(mn.group(2))
        ma = re.match(r'^\s*(\w+)\s*:=', s)
        if ma:
            mutable.add(ma.group(1))
            if ma.group(1) in bool_vars and re.match(r'^\s*na\s*$', s.split(':=', 1)[1].strip()):
                errs.append((ln, 'A', ma.group(1), 'bool نمی‌تواند na باشد (v6)'))

        # A) na()/nz() با آرگومان bool
        for m in NA_CALL.finditer(s):
            fn = m.group(1)
            if fn == 'na':
                inner = s[m.end():]
                d, j = 1, 0
                while j < len(inner) and d:
                    if inner[j] == '(':
                        d += 1
                    elif inner[j] == ')':
                        d -= 1
                    j += 1
                arg = inner[:j - 1].strip()
                base = re.match(r'^(\w+)', arg)
                if base and base.group(1) in bool_vars:
                    errs.append((ln, 'A', fn + '(' + arg[:30] + ')',
                                 'na() آرگومان bool نمی‌پذیرد (v6)'))
            else:
                arg = s[m.end():].split(',')[0].strip()
                base = re.match(r'^(\w+)', arg)
                if base and base.group(1) in bool_vars:
                    errs.append((ln, 'A', fn + '(' + arg[:30] + ', ...)',
                                 fn + '() آرگومان bool نمی‌پذیرد (v6)'))

        # B) شرط غیر bool
        mc = COND.match(s)
        if mc:
            cond = mc.group(1).strip()
            base = re.match(r'^(\w+)$', cond)
            if base and base.group(1) in numeric_vars:
                errs.append((ln, 'B', cond,
                             'int/float به‌صورت ضمنی به bool تبدیل نمی‌شود (v6)'))
        # شرطِ سه‌تایی: شناسهٔ بلافاصله پیش از «?» که عملوند مقایسه یا
        # آرگومان فراخوانی تابع نباشد.
        for m in re.finditer(r'(\w+)\s*\?', s):
            if m.group(1) not in numeric_vars:
                continue
            before = s[:m.start()].rstrip()
            if before[-2:] in ('>=', '<=', '==', '!=') or (before and before[-1] in '><'):
                continue                      # عملوند یک مقایسه است، نه شرط
            if before.endswith('(') and len(before) > 1 and (before[-2].isalnum() or before[-2] == '_'):
                continue                      # آرگومان فراخوانی تابع، مثل na(close)
            # اگر در همین بخشِ شرط، عملگر مقایسه وجود داشته باشد، شناسه فقط
            # یک عملوند حسابی است (مثل adxEff >= ntsMildAdx - hyst ? ...).
            seg = re.split(r':|(?<![<>=!])=(?!=)|\band\b|\bor\b|[,(]', before)[-1]
            if re.search(r'>=|<=|==|!=|>|<', seg):
                continue
            errs.append((ln, 'B', m.group(1) + ' ?',
                         'شرط سه‌تایی int/float است؛ در v6 به bool تبدیل نمی‌شود'))
        # C) پارامتر تکراری در یک فراخوانی
        for m in re.finditer(r'(?<![\w.])(\w+(?:\.\w+)?)\s*\(', s):
            d, j, start = 1, m.end(), m.end()
            while j < len(s) and d:
                if s[j] == '(':
                    d += 1
                elif s[j] == ')':
                    d -= 1
                j += 1
            names = named_args(s[start:j - 1])
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                errs.append((ln, 'C', m.group(1) + '(' + ', '.join(sorted(dupes)) + ')',
                             'پارامتر تکراری در یک فراخوانی (v6)'))

        # D) timeframe بدون multiplier
        for m in SEC.finditer(s):
            tf = m.group(1)
            if tf in ('D', 'W', 'M', 'S', 'h', 'min', 'sec'):
                errs.append((ln, 'D', '"' + tf + '"',
                             'در v6 مقدار timeframe باید multiplier داشته باشد (مثلاً "1D")'))

        # E) طول ta.* از متغیر mutable
        for m in TA.finditer(s):
            rest = s[m.end():]
            parts = named_args(rest.split(')')[0]) if False else None
            args = rest.split(',')
            if len(args) >= 2:
                cand = args[1].split(')')[0].strip()
                cm = re.match(r'^(\w+)$', cand)
                if cm and cm.group(1) in mutable and cm.group(1) not in inputs:
                    errs.append((ln, 'E', 'ta.' + m.group(1) + '(..., ' + cand + ')',
                                 'طول ta.* باید simple/const باشد؛ متغیر mutable در v6 '
                                 'سری محسوب می‌شود'))

        # F) offset با مقدار series
        for m in OFFSET.finditer(s):
            val = m.group(1).strip()
            vm = re.match(r'^(\w+)$', val)
            if vm and vm.group(1) in mutable and vm.group(1) not in inputs:
                errs.append((ln, 'F', 'offset = ' + val,
                             'offset مقدار series نمی‌پذیرد (v6)'))
    return errs


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'src/SMC_NTS_PRO_v6.pine'
    found = check(path)
    name = path.split('/')[-1]
    if not found:
        print('OK — قواعد ناسازگار Pine v6 در ' + name + ' رعایت شده‌اند.')
        sys.exit(0)
    for (ln, kind, what, why) in found:
        print(kind + ' | خط ' + str(ln) + ': ' + what + ' → ' + why)
    print('\n' + str(len(found)) + ' مورد در ' + name + '.')
    sys.exit(1)
