#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بررسی امضای فراخوانی built-in های Pine Script v6
=================================================
سه خطا را می‌گیرد:

  A) تعداد آرگومان موقعیتی (positional) خارج از بازهٔ مجاز تابع
     نمونهٔ واقعی این پروژه: time(timeframe.period, sess, tz, bar_index - 1)
     که time() حداکثر ۳ آرگومان می‌پذیرد.
  B) نام پارامتر نامعتبر برای آن تابع (named argument)
  C) آرگومان موقعیتی بعد از آرگومان نام‌دار (در Pine غیرمجاز است)

جدول API فقط توابعی را پوشش می‌دهد که در این اسکریپت استفاده شده‌اند و
امضایشان در مستندات رسمی v6 آمده است؛ توابع ناشناخته بی‌صدا رد می‌شوند
تا هشدار کاذب تولید نشود.

استفاده:  python3 tools/api_arity.py src/SMC_NTS_PRO_v6.pine
"""
import re
import sys
from collections import defaultdict

# name -> (min_pos, max_pos, {named})
# توجه: بازهٔ positional برابر «طول کامل امضای رسمی» است چون در Pine همهٔ
# پارامترها می‌توانند موقعیتی پاس داده شوند؛ سخت‌گیری اصلی روی توابعی است که
# امضای کوتاه و ثابت دارند (time، color.new، alert، ta.*) و روی نام پارامترها.
API = {
    # name -> (min_pos, max_pos, نام همهٔ پارامترهای مجاز به‌صورت named)
    # max_pos = طول کامل امضای رسمی، چون در Pine هر پارامتری می‌تواند موقعیتی پاس شود.
    'indicator':        (1, 11, {'title', 'shorttitle', 'overlay', 'format', 'precision',
                                 'scale', 'max_bars_back', 'max_lines_count',
                                 'max_labels_count', 'max_boxes_count',
                                 'max_polylines_count'}),
    'plot':             (1, 15, {'series', 'title', 'color', 'linewidth', 'style',
                                 'trackprice', 'histbase', 'offset', 'join', 'editable',
                                 'show_last', 'display', 'format', 'precision',
                                 'force_overlay'}),
    'plotshape':        (1, 13, {'series', 'title', 'style', 'location', 'color', 'offset',
                                 'text', 'textcolor', 'editable', 'size', 'show_last',
                                 'display', 'force_overlay'}),
    'plotchar':         (1, 13, {'series', 'title', 'char', 'location', 'color', 'offset',
                                 'text', 'textcolor', 'editable', 'size', 'show_last',
                                 'display', 'force_overlay'}),
    'alertcondition':   (1, 3, {'condition', 'title', 'message'}),
    'alert':            (1, 2, {'message', 'freq'}),
    'fill':             (2, 7, {'plot1', 'plot2', 'color', 'title', 'editable',
                                'show_last', 'fillgaps'}),
    'bgcolor':          (1, 6, {'color', 'title', 'editable', 'show_last', 'offset',
                                'display'}),
    'barcolor':         (1, 6, {'color', 'title', 'editable', 'show_last', 'offset',
                                'display'}),
    'line.new':         (4, 9, {'x1', 'y1', 'x2', 'y2', 'xloc', 'extend', 'color',
                                'style', 'width'}),
    'label.new':        (2, 12, {'x', 'y', 'text', 'xloc', 'yloc', 'color', 'style',
                                 'textcolor', 'size', 'textalign', 'tooltip',
                                 'text_font_family'}),
    'box.new':          (4, 17, {'left', 'top', 'right', 'bottom', 'border_color',
                                 'border_width', 'border_style', 'extend', 'xloc',
                                 'bgcolor', 'text', 'text_size', 'text_color',
                                 'text_halign', 'text_valign', 'text_wrap',
                                 'text_font_family'}),
    'table.new':        (3, 8, {'position', 'columns', 'rows', 'bgcolor', 'frame_color',
                                'frame_width', 'border_color', 'border_width'}),
    'table.cell':       (3, 11, {'table_id', 'column', 'row', 'text', 'text_color',
                                 'text_size', 'text_halign', 'text_valign', 'bgcolor',
                                 'height', 'width'}),
    'request.security': (3, 7, {'symbol', 'timeframe', 'expression', 'gaps', 'lookahead',
                                'currency', 'ignore_invalid_symbol'}),
    'time':             (0, 3, {'timeframe', 'session', 'timezone'}),
    'ticker.new':       (2, 4, {'prefix', 'ticker', 'session', 'adjustment'}),
    'str.tostring':     (1, 2, {'value', 'format'}),
    'str.format_time':  (2, 3, {'time', 'format', 'timezone'}),
    'str.contains':     (2, 3, {'source', 'target', 'case_sensitive'}),
    'str.upper':        (1, 2, {'source', 'case_sensitive'}),
    'str.lower':        (1, 2, {'source', 'case_sensitive'}),
    'color.new':        (2, 2, {'color', 'transp'}),
    'math.round':       (1, 2, {'number', 'precision'}),
    'math.max':         (2, 2, {'number1', 'number2'}),
    'math.min':         (2, 2, {'number1', 'number2'}),
    'ta.macd':          (4, 4, {'source', 'fastlen', 'slowlen', 'signallen'}),
    'ta.stoch':         (3, 4, {'source', 'high', 'low', 'length'}),
    'ta.pivothigh':     (2, 3, {'source', 'leftbars', 'rightbars'}),
    'ta.pivotlow':      (2, 3, {'source', 'leftbars', 'rightbars'}),
    'ta.atr':           (1, 1, {'length'}),
    'ta.rsi':           (1, 2, {'source', 'length'}),
    'ta.ema':           (2, 2, {'source', 'length'}),
    'ta.sma':           (2, 2, {'source', 'length'}),
    'ta.wma':           (2, 2, {'source', 'length'}),
    'ta.hma':           (2, 2, {'source', 'length'}),
    'ta.barssince':     (1, 1, {'condition'}),
    'ta.crossover':     (2, 2, {'source1', 'source2'}),
    'ta.crossunder':    (2, 2, {'source1', 'source2'}),
    'ta.change':        (1, 2, {'source', 'length'}),
    'ta.highest':       (1, 2, {'source', 'length'}),
    'ta.lowest':        (1, 2, {'source', 'length'}),
    'ta.highestbars':   (1, 2, {'source', 'length'}),
    'ta.lowestbars':    (1, 2, {'source', 'length'}),
    'ta.adx':           (0, 1, {'dilen'}),
    'input.bool':       (2, 7, {'defval', 'title', 'tooltip', 'group', 'inline',
                                'confirm', 'display'}),
    'input.int':        (2, 9, {'defval', 'title', 'minval', 'maxval', 'step', 'tooltip',
                                'group', 'inline', 'confirm', 'display'}),
    'input.float':      (2, 9, {'defval', 'title', 'minval', 'maxval', 'step', 'tooltip',
                                'group', 'inline', 'confirm', 'display'}),
    'input.string':     (2, 8, {'defval', 'title', 'options', 'tooltip', 'group',
                                'inline', 'confirm', 'display'}),
    'input.color':      (2, 7, {'defval', 'title', 'tooltip', 'group', 'inline',
                                'confirm', 'display'}),
    'input.session':    (2, 6, {'defval', 'title', 'tooltip', 'group', 'confirm',
                                'display'}),
    'input.source':     (2, 5, {'defval', 'title', 'tooltip', 'group', 'display'}),
    'input.timeframe':  (2, 7, {'defval', 'title', 'tooltip', 'group', 'inline',
                                'confirm', 'display'}),
}


def strip_strings_and_comments(text):
    """رشته‌ها را با placeholder هم‌اندازه خالی می‌کند و کمانت‌ها را حذف می‌کند،
    تا متن داخل رشته آرگومان شمرده نشود."""
    out = []
    for line in text.split('\n'):
        res, i, in_str = [], 0, False
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == '\\' and i + 1 < len(line):
                    res.append('  ')
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
                    res.append('"')
                else:
                    res.append(' ')
                i += 1
                continue
            if ch == '"':
                in_str = True
                res.append('"')
                i += 1
                continue
            if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break
            res.append(ch)
            i += 1
        out.append(''.join(res))
    return '\n'.join(out)


def split_args(body):
    parts, depth, cur = [], 0, ''
    for ch in body:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p for p in parts if p.strip()]


def audit(path):
    raw = open(path, encoding='utf-8').read()
    code = strip_strings_and_comments(raw)
    errs = []
    pat = re.compile(r'(?<![\w.])([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)(?![\w.])\s*\(')
    for m in pat.finditer(code):
        name = m.group(1)
        if name not in API:
            continue
        j, depth = m.end(), 1
        while j < len(code) and depth:
            if code[j] == '(':
                depth += 1
            elif code[j] == ')':
                depth -= 1
            j += 1
        args = split_args(code[m.end():j - 1])
        kinds = []
        for a in args:
            kinds.append('N' if re.match(r'^\s*[a-z_][a-z0-9_]*\s*=(?!=)', a) else 'P')
        pos = kinds.count('P')
        named = [re.match(r'^\s*([a-z_][a-z0-9_]*)\s*=(?!=)', a).group(1)
                 for a, k in zip(args, kinds) if k == 'N']
        ln = code[:m.start()].count('\n') + 1
        lo, hi, allowed = API[name]
        if not lo <= pos <= hi:
            errs.append((ln, 'A', name,
                         '%d آرگومان موقعیتی؛ مجاز %d تا %d' % (pos, lo, hi)))
        for nm in named:
            if nm not in allowed:
                errs.append((ln, 'B', name + '(' + nm + '=)',
                             'پارامتر نام‌دار نامعتبر'))
        if 'N' in kinds and 'P' in kinds[kinds.index('N') + 1:]:
            errs.append((ln, 'C', name,
                         'آرگومان موقعیتی بعد از آرگومان نام‌دار آمده است'))
    return errs


def main():
    if len(sys.argv) < 2:
        print('استفاده: python3 tools/api_arity.py FILE.pine [FILE2.pine ...]')
        return 2
    total = 0
    for path in sys.argv[1:]:
        errs = audit(path)
        by_line = defaultdict(list)
        for ln, kind, what, why in errs:
            by_line[ln].append((kind, what, why))
        for ln in sorted(by_line):
            for kind, what, why in by_line[ln]:
                print('%s | خط %d: %s → %s' % (kind, ln, what, why))
        total += len(errs)
        base = path.rsplit('/', 1)[-1]
        if errs:
            print('\n%d ایراد در %s.' % (len(errs), base))
        else:
            print('OK — امضای همهٔ فراخوانی‌های built-in در %s معتبر است.' % base)
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
