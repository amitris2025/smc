#!/usr/bin/env python3
"""پیدا کردن هر تابعی که متغیر global را با := تغییر می‌دهد (خطای Pine v6)."""
import re, sys

DECL = re.compile(r'^\s*(?:var\s+|varip\s+)?(?:int|float|bool|string|color|line|label|box|table|chart|array<[^>]+>|map<[^>]+>|matrix<[^>]+>)\s+(\w+)\s*(?::=|=)')
BARE = re.compile(r'^\s*(\w+)\s*=(?!=)')
ASSIGN = re.compile(r'^\s*(\w+)\s*:=')
FUNC = re.compile(r'^(\w+)\s*\((.*)\)\s*=>\s*(.*)$')
FUNC_OPEN = re.compile(r'^(\w+)\s*\((.*)$')

def params_of(sig):
    out = []
    for part in re.split(r',(?![^<]*>)', sig):
        m = re.search(r'(\w+)\s*$', part.strip())
        if m:
            out.append(m.group(1))
    return out

def scan(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    findings = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('//') or not ln.strip():
            i += 1; continue
        m = FUNC.match(ln)
        multi = None
        if not m and not ln[0].isspace():
            mo = FUNC_OPEN.match(ln)
            if mo:
                # جمع‌آوری امضای چندخطی
                j = i; sig = mo.group(2)
                while j < len(lines) - 1 and ') =>' not in sig and '=>' not in sig:
                    j += 1; sig += ' ' + lines[j].strip()
                if '=>' in sig:
                    m = type('M', (), {'group': lambda self, k, _n=mo.group(1), _s=sig: _n if k == 1 else _s})()
                    multi = j
        if m and not ln[0].isspace():
            name = m.group(1)
            sig = m.group(2) if m.group(2) is not None else ''
            ps = set(params_of(sig))
            start = (multi + 1) if multi else (i + 1)
            body = []
            k = start
            while k < len(lines):
                b = lines[k]
                if b.strip() == '':
                    body.append((k, b)); k += 1; continue
                if not b[0].isspace():
                    break
                body.append((k, b)); k += 1
            local = set(ps)
            for (bi, b) in body:
                d = DECL.match(b) or BARE.match(b)
                if d:
                    local.add(d.group(1))
                a = ASSIGN.match(b)
                if a and a.group(1) not in local:
                    findings.append((name, bi + 1, a.group(1), b.strip()[:70]))
            i = (k if not multi else k)
            continue
        i += 1
    return findings

if __name__ == '__main__':
    f = scan(sys.argv[1])
    if not f:
        print('OK — هیچ تابعی متغیر global را تغییر نمی‌دهد.')
        sys.exit(0)
    for (fn, ln, var, txt) in f:
        print(f'{ln}: تابع {fn}() متغیر global «{var}» را تغییر می‌دهد → {txt}')
    print(f'\n{len(f)} مورد پیدا شد.')
    sys.exit(1)
