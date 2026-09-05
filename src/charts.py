"""보고서용 SVG 차트 생성기.

PDF 인쇄가 목적이라 인터랙션 없이 정적 SVG만 만든다. 색은 보고서 양식과 맞춘다.
- 단일 계열은 범례 없이 제목이 계열을 설명 (범례 상자는 2계열 이상일 때만)
- 값 라벨은 직접 표기, 격자는 배경으로 물러나게
"""

import math

ACCENT = "#2E5E8A"   # 주 계열
SOFT = "#A8C0D4"     # 보조 / 비강조
WARN = "#B03A3A"     # 위험 강조
GRID = "#E3E3E3"
AXIS = "#9A9A9A"
INK = "#000000"
MUTED = "#666666"

# 기능축 색 — 고정 순서, 순위가 아니라 대상에 붙는다
AXIS_COLORS = {
    "A": "#2E5E8A",  # 전국 한약재 도매
    "B": "#5B9BBF",  # 새벽 청과 도매
    "C": "#8FBF9F",  # 근린 생활 소매
    "D": "#C98A5B",  # 관광·F&B 체류형
}


def use_theme(name: str) -> None:
    """차트 팔레트 교체. 보고서(기본)와 발표자료(airtable)가 색 체계가 다르다."""
    global ACCENT, SOFT, WARN, GRID, AXIS, INK, MUTED, AXIS_COLORS
    if name == "airtable":
        # 흰 캔버스 위에 먹색·대추색으로만 구성한다. 강조는 색 수가 아니라 대비로 준다.
        ACCENT, SOFT, WARN = "#2a241e", "#cdc5b9", "#8c3a1e"
        GRID, AXIS, INK, MUTED = "#ddd6cb", "#9c9285", "#2a241e", "#6b6257"
        AXIS_COLORS = {"A": "#2a241e", "B": "#2d4739", "C": "#a8bfa8", "D": "#c9722c"}
    else:
        ACCENT, SOFT, WARN = "#2E5E8A", "#A8C0D4", "#B03A3A"
        GRID, AXIS, INK, MUTED = "#E3E3E3", "#9A9A9A", "#000000", "#666666"
        AXIS_COLORS = {"A": "#2E5E8A", "B": "#5B9BBF", "C": "#8FBF9F", "D": "#C98A5B"}


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nice_ticks(vmax: float, target: int = 5) -> tuple[float, float]:
    """(눈금간격, 축최대값)을 1/2/5 계열로 고른다.

    이걸 안 쓰고 고정 간격을 쓰면, 값이 커질 때 격자선이 수백 개 그려져
    차트가 검게 뭉개진다.
    """
    if vmax <= 0:
        return 1, 1
    raw = vmax / target
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * mag
        if raw <= step:
            break
    return step, math.ceil(vmax / step) * step


def _fmt_tick(v: float, unit: str) -> str:
    if unit == "" and abs(v) >= 1000:
        return f"{v/1000:,.0f}천"
    return f"{v:,.0f}{unit}"



def _tick(v: float, span: float) -> str:
    """축 눈금 표기. 범위가 좁으면 소수점을 살려야 0으로 뭉개지지 않는다."""
    if span >= 20:
        return f"{v:,.0f}"
    if span >= 2:
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def _on_color(hex_color: str) -> str:
    """배경색 위에 얹을 글자색. 밝은 배경엔 검정, 어두운 배경엔 흰색."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if lum > 0.6 else "#FFFFFF"


def _open(w: int, h: int, label: str) -> str:
    return (
        f'<svg width="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{_esc(label)}">'
    )


def hbar(rows, *, width=620, bar_h=13, gap=7, pad_left=120, pad_right=None,
         vmax=None, unit="%", label="", highlight=None, colors=None):
    """가로 막대. rows = [(라벨, 값), ...] 이미 정렬된 상태로 넘길 것."""
    highlight = highlight or set()
    top, bottom = 12, 30
    h = top + len(rows) * (bar_h + gap) + bottom
    vmax = vmax or max(v for _, v in rows) or 1

    # 값 라벨이 오른쪽으로 삐져나가지 않도록 가장 긴 라벨 기준으로 여백을 잡는다
    if pad_right is None:
        longest = max(len(f"{v:,.1f}{unit}" if unit == "%" else f"{v:,.0f}{unit}")
                      for _, v in rows)
        pad_right = 12 + longest * 4.6
    step, tmax = _nice_ticks(vmax)
    plot_w = width - pad_left - pad_right

    out = [_open(width, h, label)]
    t = 0.0
    while t <= tmax + step / 2:
        x = pad_left + plot_w * t / tmax
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + len(rows)*(bar_h+gap) - gap + 4}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{h-12}" text-anchor="middle" font-size="7" fill="{MUTED}">{_fmt_tick(t, unit)}</text>')
        t += step

    for i, (name, val) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(plot_w * val / tmax, 1.2)
        if colors:
            fill = colors[i]
        else:
            fill = ACCENT if name in highlight else SOFT
        rx = 4 if w > 8 else 0
        out.append(f'<text x="{pad_left-6}" y="{y+bar_h-3}" text-anchor="end" font-size="7.6" fill="{INK}">{_esc(name)}</text>')
        out.append(f'<rect x="{pad_left}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="{rx}" fill="{fill}"/>')
        vtxt = f"{val:,.1f}{unit}" if unit == "%" else f"{val:,.0f}{unit}"
        out.append(f'<text x="{pad_left + w + 5:.1f}" y="{y+bar_h-3}" font-size="7.6" fill="{INK}">{vtxt}</text>')

    base_y = top + len(rows) * (bar_h + gap) - gap + 4
    out.append(f'<line x1="{pad_left}" y1="{base_y}" x2="{width-pad_right}" y2="{base_y}" stroke="{AXIS}" stroke-width="1"/>')
    out.append("</svg>")
    return "\n".join(out)


def line(series, years, *, width=620, height=230, unit="%", label="",
         events=None, vmax=None, vmin=None, legend=True):
    """꺾은선. series = [(이름, {연도: 값}, 색), ...]  events = [(연도, 설명), ...]

    vmin 을 주면 축이 0에서 시작하지 않는다. 지수처럼 값이 좁은 구간에
    몰려 있어 0 기준으로 그리면 변화가 눌려 보이는 경우에만 쓸 것.
    """
    pad_l, pad_r, pad_t, pad_b = 42, 14, 16, 46
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    y0, y1 = min(years), max(years)
    allv = [v for _, d, _ in series for v in d.values() if v is not None]
    vmax = vmax or (max(allv) if allv else 1)
    step, tmax = _nice_ticks(vmax)
    base = 0.0
    if vmin is not None:
        base = step * math.floor(vmin / step)

    def X(yr): return pad_l + pw * (yr - y0) / (y1 - y0)
    def Y(v):  return pad_t + ph * (1 - (v - base) / (tmax - base))

    out = [_open(width, height, label)]
    t = base
    while t <= tmax + step / 2:
        out.append(f'<line x1="{pad_l}" y1="{Y(t):.1f}" x2="{width-pad_r}" y2="{Y(t):.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-5}" y="{Y(t)+2.6:.1f}" text-anchor="end" font-size="7" fill="{MUTED}">{_fmt_tick(t, unit)}</text>')
        t += step

    # 사건 표시선 — 데이터 뒤, 선 앞.
    # 라벨은 층을 번갈아 두어 인접 연도끼리 겹치지 않게 하고,
    # 오른쪽 끝에 가까우면 선 왼쪽에 붙여 잘리지 않게 한다.
    for i, (yr, note) in enumerate(events or []):
        x = X(yr)
        ty = pad_t + 9 + (i % 2) * 11
        right_side = x > pad_l + pw * 0.62
        tx = x - 3 if right_side else x + 3
        anchor = "end" if right_side else "start"
        out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+ph}" stroke="{WARN}" stroke-width="0.9" stroke-dasharray="3 2" opacity="0.7"/>')
        out.append(f'<text x="{tx:.1f}" y="{ty}" text-anchor="{anchor}" font-size="6.8" fill="{WARN}">{_esc(note)}</text>')

    for yr in years:
        out.append(f'<text x="{X(yr):.1f}" y="{pad_t+ph+13}" text-anchor="middle" font-size="6.8" fill="{MUTED}">{str(yr)[2:]}</text>')
    out.append(f'<line x1="{pad_l}" y1="{pad_t+ph:.1f}" x2="{width-pad_r}" y2="{pad_t+ph:.1f}" stroke="{AXIS}" stroke-width="1"/>')

    for name, data, color in series:
        pts = [(X(yr), Y(data[yr])) for yr in years if data.get(yr) is not None]
        if not pts:
            continue
        d = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for x, y in pts:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color}" stroke="#FFFFFF" stroke-width="1.4"/>')

    if legend and len(series) > 1:
        lx = pad_l + 4
        ly = height - 8
        for name, _, color in series:
            out.append(f'<rect x="{lx}" y="{ly-6}" width="9" height="3.5" rx="1.5" fill="{color}"/>')
            out.append(f'<text x="{lx+13}" y="{ly-2.6}" font-size="7.2" fill="{INK}">{_esc(name)}</text>')
            lx += 16 + len(name) * 8.2
    out.append("</svg>")
    return "\n".join(out)


def stacked(rows, *, width=620, height=132, label="", unit="개"):
    """가로 누적 막대 1줄짜리 구성비. rows = [(이름, 값, 색), ...]"""
    total = sum(v for _, v, _ in rows) or 1
    pad_l, pad_r, top = 8, 8, 22
    pw = width - pad_l - pad_r
    bar_y, bar_h = top, 26

    out = [_open(width, height, label)]
    x = pad_l
    for name, val, color in rows:
        w = pw * val / total
        if w > 2:
            out.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{max(w-2,1):.1f}" height="{bar_h}" rx="3" fill="{color}"/>')
        if w > 34:
            out.append(f'<text x="{x + w/2:.1f}" y="{bar_y+bar_h/2+3:.1f}" text-anchor="middle" font-size="7.6" fill="#FFFFFF" font-weight="700">{val:,.0f}</text>')
        x += w

    # 범례
    lx, ly = pad_l, bar_y + bar_h + 20
    for name, val, color in rows:
        pct = val / total * 100
        out.append(f'<rect x="{lx}" y="{ly-7}" width="9" height="9" rx="2" fill="{color}"/>')
        txt = f"{name} {val:,.0f}{unit} ({pct:.1f}%)"
        out.append(f'<text x="{lx+13}" y="{ly}" font-size="7.4" fill="{INK}">{_esc(txt)}</text>')
        lx += 22 + len(txt) * 5.4
        if lx > width - 120:
            lx, ly = pad_l, ly + 15
    out.append("</svg>")
    return "\n".join(out)


def stacked_rows(rows, seg_names, seg_colors, *, width=620, bar_h=13, gap=7,
                 pad_left=120, label="", note_unit="%"):
    """행마다 100% 누적 막대. rows = [(라벨, [비율...]), ...]

    시간대 구성처럼 '합이 100인 여러 항목'을 시장끼리 비교할 때 쓴다.
    """
    top = 12
    legend_h = 26
    h = top + len(rows) * (bar_h + gap) + legend_h + 6
    pw = width - pad_left - 16

    out = [_open(width, h, label)]
    for i, (name, vals) in enumerate(rows):
        y = top + i * (bar_h + gap)
        out.append(f'<text x="{pad_left-6}" y="{y+bar_h-3}" text-anchor="end" font-size="7.6" fill="{INK}">{_esc(name)}</text>')
        x = pad_left
        total = sum(vals) or 1
        for v, color in zip(vals, seg_colors):
            w = pw * v / total
            if w > 1:
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w-1.5,0.8):.1f}" height="{bar_h}" fill="{color}"/>')
            if w > 26:
                out.append(f'<text x="{x+w/2:.1f}" y="{y+bar_h-3.5}" text-anchor="middle" font-size="6.6" fill="{_on_color(color)}">{v:.0f}</text>')
            x += w

    ly = top + len(rows) * (bar_h + gap) + 14
    lx = pad_left
    for nm, color in zip(seg_names, seg_colors):
        out.append(f'<rect x="{lx}" y="{ly-7}" width="9" height="9" rx="2" fill="{color}"/>')
        out.append(f'<text x="{lx+12}" y="{ly}" font-size="7" fill="{INK}">{_esc(nm)}</text>')
        lx += 22 + len(nm) * 5.6
    out.append("</svg>")
    return "\n".join(out)


def diverging(rows, *, width=620, bar_h=13, gap=7, pad_left=120, label="", unit="개"):
    """0을 중심으로 좌우로 뻗는 막대. 순증/순감처럼 부호가 의미 있을 때."""
    top, bottom = 12, 26
    h = top + len(rows) * (bar_h + gap) + bottom
    lo = min(0, min(v for _, v in rows))
    hi = max(0, max(v for _, v in rows))
    span = max(abs(lo), abs(hi)) or 1
    pw = width - pad_left - 40
    zero = pad_left + pw * abs(lo) / (abs(lo) + abs(hi)) if (lo < 0 < hi) else (pad_left if lo >= 0 else pad_left + pw)
    scale = pw / (abs(lo) + abs(hi)) if (abs(lo) + abs(hi)) else 1

    out = [_open(width, h, label)]
    for i, (name, val) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = abs(val) * scale
        x = zero if val >= 0 else zero - w
        color = "#5B8C6E" if val >= 0 else WARN
        out.append(f'<text x="{pad_left-6}" y="{y+bar_h-3}" text-anchor="end" font-size="7.6" fill="{INK}">{_esc(name)}</text>')
        if w > 0.5:
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w,1):.1f}" height="{bar_h}" rx="3" fill="{color}"/>')
        # 음수 막대의 라벨이 왼쪽 이름표를 침범하면 0선 오른쪽으로 넘긴다
        if val >= 0:
            tx, anchor = x + w + 4, "start"
        elif x - 4 > pad_left + 22:
            tx, anchor = x - 4, "end"
        else:
            tx, anchor = zero + 5, "start"
        # 퍼센트는 소수 첫째자리까지 보여야 차이가 드러나지만, 개수는 정수여야 한다
        decimals = unit == "%" and abs(span) < 100
        vtxt = f"{val:+,.1f}{unit}" if decimals else f"{val:+,.0f}{unit}"
        out.append(f'<text x="{tx:.1f}" y="{y+bar_h-3}" text-anchor="{anchor}" font-size="7.4" fill="{INK}">{vtxt}</text>')

    base = top + len(rows) * (bar_h + gap) - gap + 3
    out.append(f'<line x1="{zero:.1f}" y1="{top-3}" x2="{zero:.1f}" y2="{base:.1f}" stroke="{AXIS}" stroke-width="1"/>')
    out.append(f'<text x="{zero:.1f}" y="{h-10}" text-anchor="middle" font-size="7" fill="{MUTED}">0{unit}</text>')
    out.append("</svg>")
    return "\n".join(out)


def scatter(points, *, width=620, height=250, label="", xlab="", ylab="",
            xunit="%", yunit="%", quadrant=None, fit=None, diag=False):
    """산점도. points = [(라벨, x, y, 색), ...]

    quadrant=(x0,y0) 이면 기준선을 긋고, fit=(기울기, 절편) 이면 회귀선을 그린다.
    diag=True 면 y=x 대각선을 그린다(두 축이 같은 단위일 때 비교 기준).
    """
    pad_l, pad_r, pad_t, pad_b = 46, 16, 16, 40
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    x0, x1 = min(0, min(xs)), max(xs) * 1.12
    y0, y1 = min(0, min(ys)) * 1.15 if min(ys) < 0 else 0, max(ys) * 1.12

    def X(v): return pad_l + pw * (v - x0) / (x1 - x0)
    def Y(v): return pad_t + ph * (1 - (v - y0) / (y1 - y0))

    out = [_open(width, height, label)]
    for k in range(5):
        gy = pad_t + ph * k / 4
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width-pad_r}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        val = y1 - (y1 - y0) * k / 4
        out.append(f'<text x="{pad_l-5}" y="{gy+2.6:.1f}" text-anchor="end" font-size="7" fill="{MUTED}">{_tick(val, y1-y0)}{yunit}</text>')
    for k in range(5):
        gx = pad_l + pw * k / 4
        val = x0 + (x1 - x0) * k / 4
        out.append(f'<text x="{gx:.1f}" y="{pad_t+ph+13:.1f}" text-anchor="middle" font-size="7" fill="{MUTED}">{_tick(val, x1-x0)}{xunit}</text>')

    if quadrant:
        qx, qy = quadrant
        out.append(f'<line x1="{X(qx):.1f}" y1="{pad_t}" x2="{X(qx):.1f}" y2="{pad_t+ph}" stroke="{WARN}" stroke-width="0.9" stroke-dasharray="3 2" opacity="0.6"/>')
        out.append(f'<line x1="{pad_l}" y1="{Y(qy):.1f}" x2="{width-pad_r}" y2="{Y(qy):.1f}" stroke="{WARN}" stroke-width="0.9" stroke-dasharray="3 2" opacity="0.6"/>')

    if diag:
        lo, hi = max(x0, y0), min(x1, y1)
        out.append(f'<line x1="{X(lo):.1f}" y1="{Y(lo):.1f}" x2="{X(hi):.1f}" y2="{Y(hi):.1f}" '
                   f'stroke="{AXIS}" stroke-width="1" stroke-dasharray="4 3" opacity="0.7"/>')
    if fit:
        slope, intercept = fit
        out.append(f'<line x1="{X(x0):.1f}" y1="{Y(slope*x0+intercept):.1f}" '
                   f'x2="{X(x1):.1f}" y2="{Y(slope*x1+intercept):.1f}" '
                   f'stroke="{ACCENT}" stroke-width="1.6" opacity="0.85"/>')

    for name, xv, yv, color in points:
        cx, cy = X(xv), Y(yv)
        # 이름이 비면 라벨 없이 점만 찍는다 (관측치가 많아 라벨이 무의미할 때)
        r = 4.5 if name else 3.2
        op = "" if name else ' opacity="0.55"'
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" stroke="#FFFFFF" stroke-width="1.2"{op}/>')
        if not name:
            continue
        anchor = "end" if cx > pad_l + pw * 0.72 else "start"
        tx = cx - 7 if anchor == "end" else cx + 7
        out.append(f'<text x="{tx:.1f}" y="{cy+2.6:.1f}" text-anchor="{anchor}" font-size="7" fill="{INK}">{_esc(name)}</text>')

    out.append(f'<line x1="{pad_l}" y1="{pad_t+ph:.1f}" x2="{width-pad_r}" y2="{pad_t+ph:.1f}" stroke="{AXIS}" stroke-width="1"/>')
    out.append(f'<text x="{pad_l+pw/2:.1f}" y="{height-6}" text-anchor="middle" font-size="7.4" fill="{MUTED}">{_esc(xlab)}</text>')
    out.append(f'<text x="10" y="{pad_t+ph/2:.1f}" text-anchor="middle" font-size="7.4" fill="{MUTED}" transform="rotate(-90 10 {pad_t+ph/2:.1f})">{_esc(ylab)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def heatmap(rows, cols, values, *, width=620, cell_h=17, pad_left=118,
            label="", unit="%", ramp=("#F2F6F9", "#1F3F5C")):
    """행×열 격자 히트맵. values[i][j] = 행 i, 열 j 의 값.

    단일 색상 램프(밝음→어두움)로 크기를 표현한다. 무지개색은 쓰지 않는다.
    """
    pad_r, pad_t = 14, 22
    pw = width - pad_left - pad_r
    cw = pw / len(cols)
    h = pad_t + len(rows) * cell_h + 26

    flat = [v for row in values for v in row if v is not None]
    lo, hi = (min(flat), max(flat)) if flat else (0, 1)
    rng = (hi - lo) or 1

    def blend(t):
        c0 = tuple(int(ramp[0].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        c1 = tuple(int(ramp[1].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02X%02X%02X" % tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))

    out = [_open(width, h, label)]
    for j, c in enumerate(cols):
        out.append(f'<text x="{pad_left + cw*(j+0.5):.1f}" y="{pad_t-7}" text-anchor="middle" '
                   f'font-size="7" fill="{MUTED}">{_esc(c)}</text>')
    for i, r in enumerate(rows):
        y = pad_t + i * cell_h
        out.append(f'<text x="{pad_left-6}" y="{y+cell_h-5.5}" text-anchor="end" '
                   f'font-size="7.4" fill="{INK}">{_esc(r)}</text>')
        for j, v in enumerate(values[i]):
            if v is None:
                continue
            x = pad_left + cw * j
            fill = blend((v - lo) / rng)
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{cw-1.5:.1f}" height="{cell_h-1.5}" '
                       f'rx="2" fill="{fill}"/>')
            out.append(f'<text x="{x+cw/2:.1f}" y="{y+cell_h-5.5}" text-anchor="middle" '
                       f'font-size="6.4" fill="{_on_color(fill)}">{v:.0f}</text>')

    ly = pad_t + len(rows) * cell_h + 15
    out.append(f'<text x="{pad_left}" y="{ly}" font-size="6.8" fill="{MUTED}">'
               f'낮음 {lo:.0f}{unit}</text>')
    for k in range(12):
        out.append(f'<rect x="{pad_left+56+k*9:.1f}" y="{ly-7}" width="8" height="8" '
                   f'fill="{blend(k/11)}"/>')
    out.append(f'<text x="{pad_left+172}" y="{ly}" font-size="6.8" fill="{MUTED}">'
               f'{hi:.0f}{unit} 높음</text>')
    out.append("</svg>")
    return "\n".join(out)


def stat_tiles(items, *, width=620, cols=4, label=""):
    """숫자 타일. items = [(값, 단위, 설명), ...] — 규모를 한눈에 보이려는 용도."""
    rows = (len(items) + cols - 1) // cols
    tw = width / cols
    th = 58
    h = rows * th

    out = [_open(width, h, label)]
    for i, (val, unit, desc) in enumerate(items):
        x = (i % cols) * tw
        y = (i // cols) * th
        out.append(f'<rect x="{x+3:.1f}" y="{y+3}" width="{tw-6:.1f}" height="{th-8}" '
                   f'rx="4" fill="#F4F7FA" stroke="#DCE5EC" stroke-width="0.8"/>')
        out.append(f'<text x="{x+tw/2:.1f}" y="{y+28}" text-anchor="middle" font-size="16" '
                   f'font-weight="700" fill="{ACCENT}">{_esc(val)}'
                   f'<tspan font-size="9" fill="{MUTED}">{_esc(unit)}</tspan></text>')
        out.append(f'<text x="{x+tw/2:.1f}" y="{y+43}" text-anchor="middle" font-size="7.2" '
                   f'fill="{INK}">{_esc(desc)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def grouped_bars(groups, *, width=620, height=200, label="", unit="", vmax=None):
    """세로 그룹 막대. groups = [(그룹명, [(계열명, 값, 색), ...]), ...]"""
    pad_l, pad_r, pad_t, pad_b = 40, 10, 14, 40
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    allv = [v for _, items in groups for _, v, _ in items]
    vmax = vmax or (max(allv) if allv else 1)
    step = 10 ** (len(str(int(vmax))) - 1)
    tmax = ((int(vmax) // step) + 1) * step

    gw = pw / len(groups)
    out = [_open(width, height, label)]
    for t in range(0, int(tmax) + 1, int(step)):
        y = pad_t + ph * (1 - t / tmax)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-5}" y="{y+2.6:.1f}" text-anchor="end" font-size="7" fill="{MUTED}">{t:,}</text>')

    for gi, (gname, items) in enumerate(groups):
        n = len(items)
        bw = min((gw - 14) / n, 26)
        x0 = pad_l + gw * gi + (gw - bw * n) / 2
        for bi, (sname, val, color) in enumerate(items):
            bh = ph * val / tmax
            x = x0 + bw * bi
            y = pad_t + ph - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{bh:.1f}" rx="3" fill="{color}"/>')
            out.append(f'<text x="{x + (bw-2)/2:.1f}" y="{y-3:.1f}" text-anchor="middle" font-size="7" fill="{INK}">{val:,.0f}</text>')
        out.append(f'<text x="{pad_l + gw*gi + gw/2:.1f}" y="{pad_t+ph+14:.1f}" text-anchor="middle" font-size="7.4" fill="{INK}">{_esc(gname)}</text>')

    out.append(f'<line x1="{pad_l}" y1="{pad_t+ph:.1f}" x2="{width-pad_r}" y2="{pad_t+ph:.1f}" stroke="{AXIS}" stroke-width="1"/>')
    # 범례
    if groups and len(groups[0][1]) > 1:
        lx, ly = pad_l, height - 6
        for sname, _, color in groups[0][1]:
            out.append(f'<rect x="{lx}" y="{ly-7}" width="9" height="9" rx="2" fill="{color}"/>')
            out.append(f'<text x="{lx+13}" y="{ly}" font-size="7.2" fill="{INK}">{_esc(sname)}</text>')
            lx += 24 + len(sname) * 8
    out.append("</svg>")
    return "\n".join(out)
