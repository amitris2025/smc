#!/usr/bin/env python3
# =============================================================================
#  namespace_check.py — دو بررسی مربوط به سیستم نوع Pine v6
# =============================================================================
#  بررسی A: عضو نامعتبر در namespace های داخلی (مثلاً syminfo.title که در v6
#           وجود ندارد و خطای Undeclared identifier می‌دهد).
#  بررسی B: ثابت‌های «نوع یکتا» (unique value type) مانند line.style_solid،
#           label.style_label_up، size.normal، extend.right، shape.diamond،
#           plot.style_linebr و format.mintick در v6 از نوع int/string معمولی
#           نیستند. نگه‌داشتن آن‌ها در متغیری با نوع صریح (int/float/string/
#           bool/color) خطای کامپایل می‌دهد:
#             Cannot assign a value of the "series string" type to the "_style"
#             variable. The variable is declared with the "const int" type.
#           این ثابت‌ها فقط باید مستقیم به پارامتر همان built-in پاس داده شوند.
# =============================================================================
import re
import sys

# --- اعضای معتبر namespace ها (Pine v6) ---
NS_MEMBERS = {
    'syminfo': {'basecurrency', 'currency', 'description', 'mintick', 'pointvalue',
                'prefix', 'pricescale', 'root', 'session', 'ticker', 'tickerid',
                'timezone', 'type'},
    'barstate': {'isfirst', 'islast', 'islastconfirmedhistory', 'ishistory', 'isnew',
                 'isconfirmed', 'isplaying', 'ispreview', 'isrealtime'},
    'timeframe': {'period', 'multiplier', 'seconds', 'in_seconds', 'isdaily', 'isdwm',
                  'isintraday', 'ismonthly', 'isseconds', 'isweekly', 'minutes',
                  'from_seconds', 'change'},
    'xloc': {'bar_index', 'bar_time'},
    'yloc': {'price', 'bar_index'},
    'extend': {'none', 'right', 'left', 'both'},
    'barmerge': {'gaps_on', 'gaps_off', 'lookahead_on', 'lookahead_off'},
    'alert': {'freq_all', 'freq_once_per_bar', 'freq_once_per_bar_close'},
    'display': {'none', 'all', 'pane', 'price_scale', 'data_window', 'status_line'},
    'location': {'abovebar', 'belowbar', 'top', 'bottom', 'absolute'},
    'shape': {'arrowdown', 'arrowup', 'circle', 'cross', 'diamond', 'flag',
              'labeldown', 'labelup', 'square', 'triangledown', 'triangleup', 'xcross'},
    'size': {'auto', 'huge', 'large', 'normal', 'small', 'tiny'},
    'text': {'align_center', 'align_left', 'align_right', 'size_auto', 'size_huge',
             'size_large', 'size_normal', 'size_small', 'size_tiny'},
    # namespace format در v6 دقیقاً ۵ عضو دارد (مستند رسمی):
    # inherit/price/volume/percent برای پارامتر format تابع indicator() و plot()،
    # و mintick فقط برای str.tostring().
    'format': {'inherit', 'mintick', 'percent', 'price', 'volume'},
    'plot': {'style_area', 'style_areabr', 'style_circles', 'style_columns',
             'style_cross', 'style_histogram', 'style_line', 'style_linebr',
             'style_stepline', 'style_steplinebr'},
}
# namespace های سبک‌محور که فقط برای پارامتر style معتبرند
STYLE_NS = {
    'line': {'style_solid', 'style_dotted', 'style_dashed', 'style_arrow_left',
             'style_arrow_right', 'style_arrow_both'},
    'label': {'style_none', 'style_xcross', 'style_cross', 'style_triangleup',
              'style_triangledown', 'style_flag', 'style_circle', 'style_arrowup',
              'style_arrowdown', 'style_label_up', 'style_label_down',
              'style_label_left', 'style_label_right', 'style_label_center',
              'style_square', 'style_diamond', 'style_text_outline'},
}
# ثابت‌هایی که «نوع یکتا» دارند و نباید در متغیر با نوع صریح ذخیره شوند
FORMAT_PARAM_OK = {'inherit', 'price', 'volume', 'percent'}
UNIQUE_CONST = re.compile(
    r'\b(?:line|label|plot)\.style_\w+|\bshape\.\w+|\bsize\.\w+|\bextend\.\w+'
    r'|\blocation\.\w+|\bxloc\.\w+|\byloc\.\w+|\btext\.align_\w+|\bdisplay\.\w+'
    r'|\bformat\.\w+|\bbarmerge\.\w+')

TYPE_ANNOT = re.compile(
    r'^\s*(?:var\s+|varip\s+)?(int|float|bool|string|color)\s+(\w+)\s*=\s*(.+)$')


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


def depth0_unique_consts(rhs):
    """ثابت‌های نوع یکتا که در عمق کمان صفرِ سمت راست ظاهر شده‌اند."""
    hits, depth, i = [], 0, 0
    while i < len(rhs):
        c = rhs[i]
        if c in '([':
            depth += 1
        elif c in ')]':
            depth -= 1
        if depth == 0:
            m = UNIQUE_CONST.match(rhs, i)
            if m:
                hits.append(m.group(0))
                i = m.end()
                continue
        i += 1
    return hits


def check(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    errs = []
    for idx, raw in enumerate(lines, 1):
        code = strip_comment(raw)
        if not code.strip():
            continue
        # --- بررسی A: عضو نامعتبر namespace ---
        for ns, members in NS_MEMBERS.items():
            for m in re.finditer(r'(?<![\w.])' + ns + r'\.(\w+)', code):
                if m.group(1) not in members:
                    errs.append((idx, 'A', f'{ns}.{m.group(1)}',
                                 'عضو نامعتبر در namespace — خطای Undeclared identifier'))
        # برای line/label فقط ثابت‌های style_* بررسی می‌شوند؛ بقیه متدها هستند
        # (line.new، label.delete و ...) و نباید گزارش شوند.
        for ns, members in STYLE_NS.items():
            for m in re.finditer(r'(?<![\w.])' + ns + r'\.(style_\w+)', code):
                if m.group(1) not in members:
                    errs.append((idx, 'A', f'{ns}.{m.group(1)}',
                                 'ثابت style نامعتبر — خطای Undeclared identifier'))
        # --- بررسی B: ثابت نوع یکتا در متغیر با نوع صریح ---
        m = TYPE_ANNOT.match(code)
        if m:
            typ, name, rhs = m.group(1), m.group(2), m.group(3)
            hits = depth0_unique_consts(rhs)
            if hits:
                names = ', '.join(sorted(set(hits)))
                errs.append((idx, 'B', typ + ' ' + name,
                             'مقدار نوع یکتا (' + names + ') به متغیر با نوع صریح ' +
                             typ + ' نسبت داده شده — باید مستقیم به پارامتر همان ' +
                             'built-in پاس داده شود'))
        # --- بررسی D: مقدار مجاز پارامتر نام‌دار format ---
        # indicator()/strategy()/plot() و مانند آن فقط inherit/price/volume/percent
        # را می‌پذیرند؛ format.mintick مخصوص str.tostring() است.
        for m in re.finditer(r'\bformat\s*=\s*format\.(\w+)', code):
            if m.group(1) not in FORMAT_PARAM_OK:
                errs.append((idx, 'D', 'format=format.' + m.group(1),
                             'مقدار نامعتبر برای پارامتر format؛ مجاز: '
                             + ', '.join(sorted(FORMAT_PARAM_OK))))

        # --- بررسی C: ثابت نوع یکتا به‌عنوان آرگومان یک تابع کاربردی ---
        # توابع کاربردی نمی‌توانند پارامتری با نوع یکتا داشته باشند؛ پس پاس
        # دادن format.mintick / size.tiny / line.style_solid و مانند آن به یک
        # تابع تعریف‌شده توسط کاربر خطای کامپایل می‌دهد.
        for m in re.finditer(r'(?<![\w.])(f_\w+)\s*\(', code):
            j, depth = m.end(), 1
            while j < len(code) and depth:
                if code[j] == '(':
                    depth += 1
                elif code[j] == ')':
                    depth -= 1
                j += 1
            for u in UNIQUE_CONST.finditer(code[m.end():j - 1]):
                errs.append((idx, 'C', m.group(1) + '(... ' + u.group(0) + ')',
                             'ثابت نوع یکتا به تابع کاربردی پاس داده شده؛ باید مستقیم '
                             'به built-in مربوطه پاس شود یا در تابع اختصاصی کپسوله گردد'))

    return errs


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'src/SMC_NTS_PRO_v6.pine'
    found = check(path)
    name = path.split('/')[-1]
    if not found:
        print(f'OK — namespace و انواع یکتا در {name} بدون ایراد.')
        sys.exit(0)
    for (ln, kind, what, why) in found:
        print(f'{kind} | خط {ln}: {what} → {why}')
    print(f'\n{len(found)} ایراد در {name}.')
    sys.exit(1)
