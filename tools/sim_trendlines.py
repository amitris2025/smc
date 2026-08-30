#!/usr/bin/env python3
"""
sim_trendlines.py — شبیه‌سازِ مستقلِ ماژول modules/10_trendlines_pa.pine

چرا؟ چون کامپایلر رسمی تریدینگ‌ویو در این محیط در دسترس نیست. این اسکریپت
همان منطقِ M10 را (معادلِ خط‌به‌خط) روی داده‌ی مصنوعی اجرا می‌کند و یک تصویر
PNG می‌سازد تا درستیِ این قواعد چک شود:

  * سقف/کف فقط با پیوتِ تاییدشده (بدون بازترسیم/تقلب)
  * خط نزولی = دست‌کم ۲ سقفِ پایین‌تر | خط صعودی = دست‌کم ۲ کفِ بالاتر
  * لمسِ معتبر = پیوت در نوارِ تلورانسِ ATR دورِ خط + شرطِ هال (هیچ سقف/کفِ
    قبلی بالاتر/پایین‌تر از خطِ کاندید نمی‌ایستد)
  * شکست فقط با کلوزِ آن‌سوی خط
  * ۲ لمس = پیش‌نویس (خط‌چین) | ۳ لمس به بالا = تاییدشده (خط پر)

اجرا:
    python3 tools/sim_trendlines.py [output.png]
"""

from __future__ import annotations

import math
import random
import struct
import sys
import zlib
from pathlib import Path

BARS_PER_DAY = 24


# ============================================================ داده‌ی مصنوعی
def _zigzag(points):
    """درون‌یابیِ خطی بین نقاطِ لنگری (کندل, قیمت)"""
    out = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        steps = x1 - x0
        for t in range(steps):
            out.append(y0 + (y1 - y0) * t / steps)
    out.append(points[-1][1])
    return out


def make_data(seed: int = 7):
    """چهار فاز:
       1) نویزِ ابتدایی (بدون ساختار)
       2) کانالِ نزولیِ تمیز: سقف‌ها دقیقاً روی یک خط (برای خط روند نزولی)
       3) کانالِ صعودیِ تمیز: کف‌ها دقیقاً روی یک خط (برای خط روند صعودی)
       4) رالی و سپس ریزش (برای تستِ شکستِ هر دو خط)
    """
    rnd = random.Random(seed)
    closes, price = [], 2000.0
    for _ in range(70):                                    # 1) نویز
        price += rnd.gauss(0, 4.0)
        closes.append(price)

    # 2) کانال نزولی: سقف‌ها روی خط با شیب ۲۲-/۲۶ کندل
    start = len(closes)
    T, span = 26, 130
    pts, k, pb = [], 0, start
    peak0 = price + 14
    while pb < start + span:
        pts.append((pb, peak0 - 22 * k))
        tb = pb + T // 2
        if tb < start + span:
            pts.append((tb, peak0 - 22 * k - 30 - rnd.uniform(0, 12)))
        pb += T
        k += 1
    closes += _zigzag(pts)
    price = closes[-1]

    # 3) کانال صعودی: کف‌ها روی خط با شیب ۱۸+/۲۴ کندل
    start = len(closes)
    T, span = 24, 120
    pts, k, tb = [], 0, start
    low0 = price - 12
    while tb < start + span:
        pts.append((tb, low0 + 18 * k))
        pbk = tb + T // 2
        if pbk < start + span:
            pts.append((pbk, low0 + 18 * k + 30 + rnd.uniform(0, 12)))
        tb += T
        k += 1
    closes += _zigzag(pts)
    price = closes[-1]

    # 4) رالی (شکستِ خط نزولی) و سپس ریزش (شکستِ خط صعودی)
    for _ in range(55):
        price += rnd.gauss(3.2, 3.0)
        closes.append(price)
    for _ in range(55):
        price += rnd.gauss(-3.4, 3.2)
        closes.append(price)

    bars, prev = [], closes[0]
    for c in closes:
        o = prev
        bars.append((o, max(o, c) + abs(rnd.gauss(0, 1.1)),
                     min(o, c) - abs(rnd.gauss(0, 1.1)), c))
        prev = c
    return bars


def true_range(bars):
    out = []
    for i, (_o, h, l, _c) in enumerate(bars):
        out.append(h - l if i == 0 else
                   max(h - l, abs(h - bars[i - 1][3]), abs(l - bars[i - 1][3])))
    return out


def rma(vals, period):
    out, prev, alpha = [], float("nan"), 1.0 / period
    for v in vals:
        prev = v if math.isnan(prev) else prev + alpha * (v - prev)
        out.append(prev)
    return out


def daily_levels(bars):
    """Previous Daily High / Low / Equilibrium برای هر کندل"""
    n = len(bars)
    pdh, pdl, peq = [float("nan")] * n, [float("nan")] * n, [float("nan")] * n
    days = n // BARS_PER_DAY
    for d in range(1, days + 1):
        a, b = d * BARS_PER_DAY, min((d + 1) * BARS_PER_DAY, n)
        hi = max(x[1] for x in bars[(d - 1) * BARS_PER_DAY:a])
        lo = min(x[2] for x in bars[(d - 1) * BARS_PER_DAY:a])
        for i in range(a, b):
            pdh[i], pdl[i], peq[i] = hi, lo, (hi + lo) / 2
    return pdh, pdl, peq


# ============================================================ موتورِ M10
class Engine:
    def __init__(self, left=5, right=3, basis="close", min_touch=2, tol_atr=0.35,
                 brk_atr=0.10, reanchor=True, pd_mode="emphasis"):
        self.L, self.R = left, right
        self.basis = basis
        self.min_touch = min_touch
        self.tol_atr, self.brk_atr = tol_atr, brk_atr
        self.reanchor = reanchor
        self.pd_mode = pd_mode
        self.lines = []            # همه‌ی خطوطِ ساخته‌شده (برای رسم)
        self.events = []           # (bar, kind, which)

    @staticmethod
    def line_y(x1, y1, x2, y2, xt):
        dx = x2 - x1
        return None if dx == 0 else y1 + (y2 - y1) * (xt - x1) / dx

    def run(self, bars, atr, peq):
        n = len(bars)
        st = {
            "dn": dict(bars=[], pxs=[], live=False, align=False, kill=None, obj=None),
            "up": dict(bars=[], pxs=[], live=False, align=False, kill=None, obj=None),
        }

        def new_state(kind):
            return dict(bars=[], pxs=[], live=False, align=False, kill=None, obj=None)

        for i in range(n):
            _o, h, l, c = bars[i]
            tol = self.tol_atr * atr[i]
            brk = self.brk_atr * atr[i]
            eq = peq[i]
            in_prem = (not math.isnan(eq)) and c > eq
            in_disc = (not math.isnan(eq)) and c < eq

            # ---------- پیوت‌های تاییدشده ----------
            ph = pl = None
            if self.L + self.R <= i <= n - 1 - self.L + self.R:
                j = i - self.R
                if all(bars[j][1] >= bars[k][1] for k in range(j - self.L, j + self.L + 1)):
                    ph = bars[j][1]
                if all(bars[j][2] <= bars[k][2] for k in range(j - self.L, j + self.L + 1)):
                    pl = bars[j][2]

            # ================= خط نزولی (سقف‌های پایین‌تر) =================
            d = st["dn"]
            if ph is not None:
                px, bx = ph, i - self.R
                src_h = bars[bx][3] if self.basis == "close" else px
                eq_b = peq[bx]
                in_prem_b = (not math.isnan(eq_b)) and bars[bx][3] > eq_b
                hits = len(d["bars"])
                if hits == 0:
                    d["bars"].append(bx); d["pxs"].append(px)
                    d["x1"], d["y1"] = bx, px
                    d["live"] = False
                elif hits == 1:
                    if px < d["y1"]:
                        if self.pd_mode != "only" or in_prem_b:
                            d["bars"].append(bx); d["pxs"].append(px)
                            d["x2"], d["y2"] = bx, px
                            d["live"], d["align"] = True, in_prem_b
                            self.events.append((i, "touch", "dn"))
                    else:
                        d["bars"], d["pxs"] = [bx], [px]
                        d["x1"], d["y1"] = bx, px
                        d["live"] = False
                else:
                    y_at = self.line_y(d["x1"], d["y1"], d["x2"], d["y2"], bx)
                    if y_at is None:
                        d["bars"], d["pxs"], d["live"] = [], [], False
                    elif src_h > y_at + brk:                       # ---- ابطال ----
                        d["kill"] = (bx, y_at)
                        d["live"] = False
                        self.events.append((i, "break", "dn"))
                        d["bars"], d["pxs"] = [], []
                        if px >= d["y2"]:
                            d["bars"], d["pxs"] = [bx], [px]
                            d["x1"], d["y1"] = bx, px
                        else:
                            d["bars"] = [d["x2"], bx]; d["pxs"] = [d["y2"], px]
                            d["x1"], d["y1"] = d["x2"], d["y2"]
                            d["x2"], d["y2"] = bx, px
                            d["live"], d["align"] = True, in_prem_b
                    else:                                          # ---- لمس ----
                        need_re = False
                        if px <= y_at + tol:
                            ok = (self.pd_mode != "only") or in_prem_b
                            for k in range(len(d["bars"])):
                                yy = self.line_y(d["x1"], d["y1"], bx, px, d["bars"][k])
                                if yy is not None and d["pxs"][k] > yy + tol:
                                    ok = False
                            if ok:
                                d["bars"].append(bx); d["pxs"].append(px)
                                d["x2"], d["y2"] = bx, px
                                d["align"] = d["align"] or in_prem_b
                                self.events.append((i, "touch", "dn"))
                            else:
                                need_re = True
                        else:
                            need_re = True
                        if need_re and self.reanchor and px < d["y2"]:
                            if len(d["bars"]) >= 3 and d["obj"] is not None:
                                d["obj"]["end"] = (d["x2"], d["y2"])
                                d["obj"]["broken"] = True
                                d["obj"] = None
                            d["bars"] = [d["x2"], bx]; d["pxs"] = [d["y2"], px]
                            d["x1"], d["y1"] = d["x2"], d["y2"]
                            d["x2"], d["y2"] = bx, px
                            d["align"] = in_prem_b

            # ================= خط صعودی (کف‌های بالاتر) =================
            u = st["up"]
            if pl is not None:
                qx, qb = pl, i - self.R
                src_l = bars[qb][3] if self.basis == "close" else qx
                eq_b = peq[qb]
                in_disc_b = (not math.isnan(eq_b)) and bars[qb][3] < eq_b
                hits = len(u["bars"])
                if hits == 0:
                    u["bars"].append(qb); u["pxs"].append(qx)
                    u["x1"], u["y1"] = qb, qx
                    u["live"] = False
                elif hits == 1:
                    if qx > u["y1"]:
                        if self.pd_mode != "only" or in_disc_b:
                            u["bars"].append(qb); u["pxs"].append(qx)
                            u["x2"], u["y2"] = qb, qx
                            u["live"], u["align"] = True, in_disc_b
                            self.events.append((i, "touch", "up"))
                    else:
                        u["bars"], u["pxs"] = [qb], [qx]
                        u["x1"], u["y1"] = qb, qx
                        u["live"] = False
                else:
                    u_at = self.line_y(u["x1"], u["y1"], u["x2"], u["y2"], qb)
                    if u_at is None:
                        u["bars"], u["pxs"], u["live"] = [], [], False
                    elif src_l < u_at - brk:                       # ---- ابطال ----
                        u["kill"] = (qb, u_at)
                        u["live"] = False
                        self.events.append((i, "break", "up"))
                        u["bars"], u["pxs"] = [], []
                        if qx <= u["y2"]:
                            u["bars"], u["pxs"] = [qb], [qx]
                            u["x1"], u["y1"] = qb, qx
                        else:
                            u["bars"] = [u["x2"], qb]; u["pxs"] = [u["y2"], qx]
                            u["x1"], u["y1"] = u["x2"], u["y2"]
                            u["x2"], u["y2"] = qb, qx
                            u["live"], u["align"] = True, in_disc_b
                    else:                                          # ---- لمس ----
                        need_up = False
                        if qx >= u_at - tol:
                            ok = (self.pd_mode != "only") or in_disc_b
                            for k in range(len(u["bars"])):
                                uu = self.line_y(u["x1"], u["y1"], qb, qx, u["bars"][k])
                                if uu is not None and u["pxs"][k] < uu - tol:
                                    ok = False
                            if ok:
                                u["bars"].append(qb); u["pxs"].append(qx)
                                u["x2"], u["y2"] = qb, qx
                                u["align"] = u["align"] or in_disc_b
                                self.events.append((i, "touch", "up"))
                            else:
                                need_up = True
                        else:
                            need_up = True
                        if need_up and self.reanchor and qx > u["y2"]:
                            if len(u["bars"]) >= 3 and u["obj"] is not None:
                                u["obj"]["end"] = (u["x2"], u["y2"])
                                u["obj"]["broken"] = True
                                u["obj"] = None
                            u["bars"] = [u["x2"], qb]; u["pxs"] = [u["y2"], qx]
                            u["x1"], u["y1"] = u["x2"], u["y2"]
                            u["x2"], u["y2"] = qb, qx
                            u["align"] = in_disc_b

            # ---------- شکست روی کندل جاری ----------
            src_up = c if self.basis == "close" else h
            src_dn = c if self.basis == "close" else l
            if d["live"] and len(d["bars"]) >= 2:
                y_now = self.line_y(d["x1"], d["y1"], d["x2"], d["y2"], i)
                if y_now is not None and i > d["x2"] and src_up > y_now + brk:
                    d["kill"] = (i, y_now)
                    d["live"] = False
                    self.events.append((i, "break", "dn"))
                    d["bars"], d["pxs"] = [i], [h]
                    d["x1"], d["y1"] = i, h
                    d["x2"], d["y2"] = i, h
            if u["live"] and len(u["bars"]) >= 2:
                u_now = self.line_y(u["x1"], u["y1"], u["x2"], u["y2"], i)
                if u_now is not None and i > u["x2"] and src_dn < u_now - brk:
                    u["kill"] = (i, u_now)
                    u["live"] = False
                    self.events.append((i, "break", "up"))
                    u["bars"], u["pxs"] = [i], [l]
                    u["x1"], u["y1"] = i, l
                    u["x2"], u["y2"] = i, l

            # ---------- ترسیم / بایگانی ----------
            for kind, s in (("dn", st["dn"]), ("up", st["up"])):
                if s["live"] and len(s["bars"]) >= self.min_touch:
                    if s["obj"] is None:
                        s["obj"] = {"kind": kind, "pts": list(zip(s["bars"], s["pxs"])),
                                    "broken": False, "end": None}
                        self.lines.append(s["obj"])
                    else:
                        s["obj"]["pts"] = list(zip(s["bars"], s["pxs"]))
                    s["obj"]["align"] = s["align"]
                elif s["obj"] is not None:
                    s["obj"]["end"] = s["kill"] if s["kill"] else (s.get("x2"), s.get("y2"))
                    s["obj"]["broken"] = True
                    s["obj"] = None
                    s["kill"] = None
        return self

    def summary(self):
        rows = []
        for ln in self.lines:
            pts = ln["pts"]
            rows.append((("نزولی" if ln["kind"] == "dn" else "صعودی"), len(pts),
                         pts[0][0], pts[-1][0],
                         "تاییدشده" if len(pts) >= 3 else "پیش‌نویس",
                         "شکسته/بایگانی" if ln["broken"] else "فعال",
                         "همسو با PD" if ln.get("align") else "-"))
        return rows


# ============================================================ رندررِ PNG
FONT3x5 = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "001", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
    "-": ["000", "000", "111", "000", "000"],
}


class Canvas:
    def __init__(self, w, h, bg=(16, 20, 24)):
        self.w, self.h = w, h
        self.buf = bytearray(bytes(bg) * (w * h))

    def px(self, x, y, col):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(col)

    def rect(self, x0, y0, x1, y1, col):
        for y in range(int(min(y0, y1)), int(max(y0, y1)) + 1):
            for x in range(int(min(x0, x1)), int(max(x0, x1)) + 1):
                self.px(x, y, col)

    def line(self, x0, y0, x1, y1, col, width=1, dash=None):
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(int(dist * 2) + 1, 1)
        half = max(width // 2, 0)
        for s in range(steps + 1):
            t = s / steps
            if dash and (int(t * dist) % (dash[0] + dash[1])) > dash[0]:
                continue
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    self.px(x + dx, y + dy, col)

    def circle(self, cx, cy, r, col):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    self.px(cx + dx, cy + dy, col)

    def text(self, x, y, s, col, scale=2):
        cx = x
        for ch in s:
            glyph = FONT3x5.get(ch)
            if glyph is None:
                cx += 4 * scale
                continue
            for r, row in enumerate(glyph):
                for cidx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cx + cidx * scale, y + r * scale,
                                  cx + cidx * scale + scale - 1,
                                  y + r * scale + scale - 1, col)
            cx += 4 * scale
        return cx

    def png(self, path: Path):
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)
            raw += self.buf[y * stride:(y + 1) * stride]

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data +
                    struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        out = b"\x89PNG\r\n\x1a\n"
        out += chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
        out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        out += chunk(b"IEND", b"")
        path.write_bytes(out)
        return path


def render(bars, eng, pdh, pdl, peq, path: Path):
    W, H = 1600, 820
    pad_l, pad_r, pad_t, pad_b = 70, 210, 40, 70
    n = len(bars)
    lo, hi = min(b[2] for b in bars), max(b[1] for b in bars)
    span = (hi - lo) or 1.0
    X = lambda i: pad_l + i * (W - pad_l - pad_r) / max(n - 1, 1)
    Y = lambda p: pad_t + (hi - p) * (H - pad_t - pad_b) / span
    cv = Canvas(W, H)

    # نواحی پریمیوم / دیسکانتِ روزِ قبل
    for d in range(n // BARS_PER_DAY):
        a, b = d * BARS_PER_DAY, min((d + 1) * BARS_PER_DAY, n)
        if math.isnan(peq[a]) or a == b:
            continue
        cv.rect(X(a), Y(peq[a]), X(b - 1), Y(pdh[a]), (58, 26, 30))     # پریمیوم
        cv.rect(X(a), Y(pdl[a]), X(b - 1), Y(peq[a]), (22, 46, 32))     # دیسکانت
        cv.line(X(a), Y(peq[a]), X(b - 1), Y(peq[a]), (150, 100, 40), 1, (1, 5))
        cv.line(X(a), Y(pdh[a]), X(b - 1), Y(pdh[a]), (70, 74, 82), 1, (2, 6))
        cv.line(X(a), Y(pdl[a]), X(b - 1), Y(pdl[a]), (70, 74, 82), 1, (2, 6))

    # کندل‌ها
    bw = max(1.5, (W - pad_l - pad_r) / n * 0.6)
    for i, (o, h, l, c) in enumerate(bars):
        col = (56, 190, 118) if c >= o else (224, 82, 82)
        x = X(i)
        cv.line(x, Y(h), x, Y(l), col, 1)
        cv.rect(x - bw / 2, Y(max(o, c)), x + bw / 2, Y(min(o, c)), col)

    # خطوطِ روند
    for ln in eng.lines:
        kind = ln["kind"]
        base_col = (232, 78, 78) if kind == "dn" else (35, 193, 168)
        col = base_col if ln.get("align", True) else (120, 124, 132)
        pts = ln["pts"]
        if ln["broken"]:
            (ex, ey) = ln["end"] if ln["end"] else pts[-1]
            cv.line(X(pts[0][0]), Y(pts[0][1]), X(ex), Y(ey), (125, 130, 138), 1, (2, 5))
            continue
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        sl = (y2 - y1) / max(x2 - x1, 1e-9)
        xe, ye = n - 1, y2 + sl * (n - 1 - x2)
        dash = (9, 6) if len(pts) < 3 else None
        cv.line(X(x1), Y(y1), X(xe), Y(ye), col, 3 if len(pts) >= 3 else 2, dash)
        for (bx, by) in pts:
            cv.circle(X(bx), Y(by), 5, col)
            cv.circle(X(bx), Y(by), 2, (16, 20, 24))
        cv.text(X(x2) - 4, Y(y2) - 24, str(len(pts)), (255, 255, 255), 2)

    # نشانگرِ شکست
    for (bar, kind, which) in eng.events:
        if kind != "break":
            continue
        y = Y(bars[bar][1] if which == "dn" else bars[bar][2])
        col = (142, 240, 160) if which == "dn" else (240, 142, 142)
        x = X(bar)
        if which == "dn":
            cv.line(x, y - 12, x - 7, y - 24, col, 2)
            cv.line(x, y - 12, x + 7, y - 24, col, 2)
            cv.line(x - 7, y - 24, x + 7, y - 24, col, 2)
        else:
            cv.line(x, y + 12, x - 7, y + 24, col, 2)
            cv.line(x, y + 12, x + 7, y + 24, col, 2)
            cv.line(x - 7, y + 24, x + 7, y + 24, col, 2)

    # راهنما
    lx, ly = W - pad_r + 14, 60
    cv.text(lx, ly, "2", (255, 255, 255), 2)
    cv.line(lx + 16, ly + 5, lx + 60, ly + 5, (232, 78, 78), 2, (9, 6))
    cv.text(lx + 68, ly, "-", (200, 200, 200), 2)
    return cv.png(path)


def main(argv):
    out_path = Path(argv[1]) if len(argv) > 1 else Path("tools/sample_trendlines.png")
    bars = make_data()
    atr = rma(true_range(bars), 14)
    pdh, pdl, peq = daily_levels(bars)
    eng = Engine().run(bars, atr, peq)

    print(f"کندل‌ها: {len(bars)}")
    print(f"{'نوع':<8}{'تعداد لمس':>10}{'از کندل':>10}{'تا کندل':>10}  وضعیت")
    for kind, hits, b0, b1, state, live, align in eng.summary():
        print(f"{kind:<8}{hits:>10}{b0:>10}{b1:>10}  {state} / {live} / {align}")
    print(f"\nتعداد شکست‌ها: {sum(1 for e in eng.events if e[1] == 'break')}")
    print("PNG خروجی:", render(bars, eng, pdh, pdl, peq, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
