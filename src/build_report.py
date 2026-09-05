"""분석 결과 → 보고서 HTML 생성.

수치를 본문에 하드코딩하지 않고 데이터에서 계산해 넣는다. 데이터가 갱신되면
다시 실행하는 것만으로 표·차트·문장의 숫자가 함께 갱신된다.

    uv run python src/build_report.py
    # 이후 Chrome 헤드리스로 PDF 변환 (README 참조)
"""

import pandas as pd

import charts as C
from config import DATA_PROCESSED, ROOT

OUT = ROOT / "output" / "report.html"

AXIS_LABEL = {
    "A": "전국 한약재 도매",
    "B": "새벽 청과 도매",
    "C": "근린 생활 소매",
    "D": "관광·F&B 체류형",
}
LATEST = 2023


def load():
    ts = pd.read_csv(DATA_PROCESSED / "vacancy_timeseries.csv")
    master = pd.read_csv(DATA_PROCESSED / "markets_enriched.csv")
    axis_of = dict(zip(master.market_name, master.axis))
    ts["axis"] = ts.market.map(axis_of)
    return ts, master


def fmt(n, d=0):
    return f"{n:,.{d}f}"


def build():
    ts, master = load()
    years = sorted(ts.year.unique())
    cur = ts[ts.year == LATEST].sort_values("vacancy_rate", ascending=False)

    # ---- 클러스터 집계 ----
    agg = ts.groupby("year").agg(total=("total", "sum"), vacant=("vacant", "sum"))
    agg["rate"] = agg.vacant / agg.total * 100
    cur_total, cur_vacant = cur.total.sum(), cur.vacant.sum()
    cur_rate = cur_vacant / cur_total * 100

    # 공실 집중도 — 1위 단독과 상위 2개 합계를 구분해서 쓴다
    top2 = cur.nlargest(2, "vacant")
    top1_name = top2.iloc[0].market
    top1_share = top2.iloc[0].vacant / cur_vacant * 100
    top2_share = top2.vacant.sum() / cur_vacant * 100

    # ---- 차트 ----
    fig_cluster = C.line(
        [("클러스터 공실률", dict(zip(agg.index, agg.rate)), C.ACCENT)],
        years, label="클러스터 전체 공실률 추이 2006~2023", unit="%", legend=False,
    )

    kd = ts[ts.market == "경동시장"].set_index("year").vacancy_rate.to_dict()
    cd = ts[ts.market == "청량리전통시장"].set_index("year").vacancy_rate.to_dict()
    fig_two = C.line(
        [("경동시장", kd, C.WARN), ("청량리전통시장", cd, C.ACCENT)],
        years, height=246, unit="%",
        label="경동시장과 청량리전통시장 공실률 추이 비교",
        events=[(2020, "공실 급등"), (2021, "건물 인수"), (2022, "스타벅스 개점")],
    )

    fig_cur = C.hbar(
        [(r.market, r.vacancy_rate) for r in cur.itertuples()],
        label=f"{LATEST}년 시장별 공실률",
        highlight={"경동시장"},
    )

    others = cur_vacant - top2.vacant.sum()
    fig_conc = C.stacked(
        [(top2.iloc[0].market, top2.iloc[0].vacant, C.WARN),
         (top2.iloc[1].market, top2.iloc[1].vacant, "#D98B8B"),
         ("나머지 8개 시장 합계", others, C.SOFT)],
        label="공실 집중도", height=118,
    )

    ax = cur.groupby("axis").agg(total=("total", "sum"), vacant=("vacant", "sum"),
                                 n=("market", "count")).reindex(["A", "B", "C", "D"]).fillna(0)
    ax["rate"] = (ax.vacant / ax.total * 100).fillna(0)
    fig_axis_mix = C.stacked(
        [(AXIS_LABEL[k], ax.loc[k, "total"], C.AXIS_COLORS[k]) for k in ["A", "B", "C", "D"]],
        label="기능축별 점포 구성", height=130,
    )
    fig_axis_rate = C.hbar(
        [(AXIS_LABEL[k], ax.loc[k, "rate"]) for k in ["A", "B", "C", "D"]],
        label="기능축별 공실률",
        colors=[C.AXIS_COLORS[k] for k in ["A", "B", "C", "D"]],
    )

    # 규모 차트도 본문과 같은 2023년 기준으로 맞춘다 (master는 2021년 자료)
    size = cur.sort_values("total", ascending=False)
    fig_size = C.hbar(
        [(r.market, r.total) for r in size.itertuples()],
        label="시장별 점포 규모", unit="개",
        colors=[C.AXIS_COLORS[a] for a in size.axis],
    )

    m2 = master[master.stores_total > 0].copy()
    m2["per_store"] = m2.merchants_total / m2.stores_total
    m2 = m2.sort_values("per_store", ascending=False)
    fig_density = C.hbar(
        [(r.market_name, r.per_store) for r in m2.itertuples()],
        label="점포당 상인 수", unit="명",
        colors=[C.AXIS_COLORS[a] for a in m2.axis],
    )

    stalls = master[master.street_stalls > 0].sort_values("street_stalls", ascending=False)
    fig_stalls = C.hbar(
        [(r.market_name, r.street_stalls) for r in stalls.itertuples()],
        label="시장별 노점 수", unit="개",
        colors=[C.AXIS_COLORS[a] for a in stalls.axis],
    )

    # ---- 표 ----
    def row_cur(r):
        cls = ' class="hi"' if r.vacancy_rate >= 5 else ""
        warn = ' class="num warn"' if r.vacancy_rate >= 5 else ' class="num"'
        return (f"<tr{cls}><td>{r.market}</td><td class='ctr'>{r.axis}</td>"
                f"<td class='num'>{fmt(r.total)}</td><td class='num'>{fmt(r.vacant)}</td>"
                f"<td{warn}>{r.vacancy_rate:.1f}%</td></tr>")

    tbl_cur = "\n".join(row_cur(r) for r in cur.itertuples())

    pivot = ts.pivot_table(index="market", columns="year", values="vacancy_rate")
    show_years = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]
    hdr = "".join(f"<th>{y}</th>" for y in show_years)
    body = []
    for m in pivot.index:
        cells = []
        for y in show_years:
            v = pivot.loc[m, y] if y in pivot.columns else None
            if pd.isna(v):
                cells.append("<td class='num'>—</td>")
            else:
                c = " warn" if v >= 20 else ""
                cells.append(f"<td class='num{c}'>{v:.1f}</td>")
        body.append(f"<tr><td>{m}</td>{''.join(cells)}</tr>")
    tbl_pivot = "\n".join(body)

    # ================= 매출 분석 (상권분석서비스) =================
    q = pd.read_csv(DATA_PROCESSED / "golmok_quarterly_sales.csv", dtype={"quarter": str})
    q["year"] = q.quarter.str[:4].astype(int)
    ysales = q.groupby(["market", "year"])["당월_매출_금액"].sum().unstack() / 1e8
    growth = ((ysales[2025] / ysales[2021] - 1) * 100).sort_values(ascending=False)

    axis_of_mkt = dict(zip(master.market_name, master.axis))
    # 약령시가 유일한 마이너스라 0을 기준으로 갈리는 diverging 이 맞다
    fig_growth = C.diverging(
        [(m, v) for m, v in growth.sort_values().items()],
        label="2021→2025 매출 성장률", unit="%",
    )

    sale_years = sorted(ysales.columns)
    big = ysales.loc[ysales[2025].nlargest(4).index]
    fig_sales_trend = C.line(
        [(m, dict(zip(sale_years, big.loc[m])), c)
         for m, c in zip(big.index, ["#2E5E8A", "#5B9BBF", "#8FBF9F", "#C98A5B"])],
        sale_years, height=214, unit="", label="주요 시장 연매출 추이",
    )

    # 시간대별 매출 구성 — 4축 가설의 직접 검증
    tp = pd.read_csv(DATA_PROCESSED / "golmok_time_profile.csv")
    bands = ["00~06", "06~11", "11~14", "14~17", "17~21", "21~24"]
    band_colors = ["#1F3F5C", "#2E5E8A", "#5B9BBF", "#8FBF9F", "#C98A5B", "#8C5B7A"]
    tp = tp.sort_values("axis")
    fig_time = C.stacked_rows(
        [(row["market"], [row[b] for b in bands]) for _, row in tp.iterrows()],
        bands, band_colors, label="시장별 시간대 매출 구성",
    )

    # 청년층(20~30대) 비중 변화
    age = pd.read_csv(DATA_PROCESSED / "golmok_age_by_year.csv")
    a21 = age[age.year == 2021].set_index("market")["청년층"]
    a25 = age[age.year == 2025].set_index("market")["청년층"]
    delta = (a25 - a21).sort_values()
    fig_age = C.diverging(
        [(m, v) for m, v in delta.items()],
        label="20~30대 매출 비중 변화 2021→2025", unit="%p",
    )

    # 공실률(2023) × 매출성장률 — 약령시 역설
    vac23 = cur.set_index("market").vacancy_rate
    pts = []
    for m in growth.index:
        if m in vac23.index:
            pts.append((m, float(vac23[m]), float(growth[m]),
                        C.AXIS_COLORS.get(axis_of_mkt.get(m, "A"), C.SOFT)))
    fig_paradox = C.scatter(
        pts, label="공실률과 매출 성장률", xlab="2023년 공실률 (%)",
        ylab="2021→2025 매출 성장률 (%)", quadrant=(10, 0), height=258,
    )

    # 개·폐업 순증 누적
    turn = pd.read_csv(DATA_PROCESSED / "golmok_store_turnover.csv")
    net = turn.groupby("market")["순증"].sum().sort_values()
    fig_net = C.diverging(
        [(m, v) for m, v in net.items()],
        label="2021~2025 점포 순증", unit="개",
    )

    # ================= 생활인구 (배후인구 변화) =================
    lp = pd.read_csv(DATA_PROCESSED / "local_people_hourly.csv", dtype={"ym": str})
    # 03~05시는 대부분 집에 있는 시간이라 상주인구의 대리 지표로 쓴다
    night = lp[lp.hour.between(3, 5)].groupby(["ym", "dong"])["pop"].mean().unstack()
    night_y = night.copy()
    night_y.index = night_y.index.str[:4].astype(int)
    night_y = night_y.groupby(level=0).mean()

    lp_years = [y for y in night_y.index if 2017 <= y <= 2026]
    fig_night = C.line(
        [(m, {y: float(night_y.loc[y, m]) for y in lp_years}, c)
         for m, c in zip(["전농1동", "용신동", "제기동", "청량리동"],
                         ["#5B8C6E", "#5B9BBF", "#B03A3A", "#C98A5B"])],
        lp_years, height=224, unit="", label="행정동별 야간 생활인구 추이",
    )

    # 입주(2023.5~7) 전후 6개월 비교
    pre = night.loc["202211":"202304"].mean()
    post = night.loc["202308":"202401"].mean()
    movein = ((post - pre) / pre * 100).sort_values()
    fig_movein = C.diverging(
        [(d, float(v)) for d, v in movein.items()],
        label="2023년 입주 전후 야간인구 증감", unit="%",
    )

    # 시간대 프로파일 (최신월, 클러스터 3개 동)
    latest_ym = lp.ym.max()
    prof = lp[(lp.ym == latest_ym) & (lp.dong.isin(["청량리동", "제기동", "용신동"]))]
    prof_p = prof.pivot_table(index="hour", columns="dong", values="pop")
    prof_idx = (prof_p / prof_p.min() * 100)  # 각 동의 최저시간=100 으로 지수화
    fig_profile = C.line(
        [(d, {h: float(prof_idx.loc[h, d]) for h in range(24)}, c)
         for d, c in zip(["청량리동", "제기동", "용신동"], ["#C98A5B", "#B03A3A", "#2E5E8A"])],
        list(range(24)), height=224, unit="", label="시간대별 생활인구 지수",
        vmin=100,  # 지수라 100 근처에 몰려 있어 0부터 그리면 변화가 안 보인다
    )

    jn_chg = float(movein.get("전농1동", 0))
    jg_chg = float(movein.get("제기동", 0))
    jn_25 = ((night_y.loc[2025, "전농1동"] / night_y.loc[2022, "전농1동"] - 1) * 100)
    jg_25 = ((night_y.loc[2025, "제기동"] / night_y.loc[2022, "제기동"] - 1) * 100)
    cl_ratio = float(prof_p["청량리동"].max() / prof_p["청량리동"].min())
    jg_ratio = float(prof_p["제기동"].max() / prof_p["제기동"].min())
    n_months = lp.ym.nunique()

    # ================= 추가 분석 =================
    # 연령대별 배후인구 변화 — 줄어든 인구가 누구인지
    ash = pd.read_csv(DATA_PROCESSED / "pop_age_shift.csv", index_col=0)
    bands4 = ["0-19", "20-39", "40-59", "60+"]
    band_cols = ["#8FBF9F", "#5B9BBF", "#2E5E8A", "#B03A3A"]
    # 증감이라 부호가 핵심이므로 0을 기준으로 갈리는 diverging 을 쓴다
    fig_agepop = C.diverging(
        [(f"{d} · {b}", float(ash.loc[d, f"{b}_변화율"]))
         for d in ["제기동", "청량리동", "용신동", "전농1동"] for b in bands4],
        pad_left=150, label="행정동별 연령대 야간인구 변화", unit="%",
    )
    jg60 = float(ash.loc["제기동", "60+_변화율"])
    jg60_n = float(ash.loc["제기동", "60+_2025"] - ash.loc["제기동", "60+_2022"])
    cl60 = float(ash.loc["청량리동", "60+_변화율"])

    # 요일별 매출 구성
    dw = pd.read_csv(DATA_PROCESSED / "sales_dow.csv", index_col=0).sort_values("주말비중")
    dow_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    dow_colors = ["#DCE5EC", "#C3D3DF", "#A8C0D4", "#8FAFC7", "#5B9BBF", "#2E5E8A", "#1F3F5C"]
    fig_dow = C.stacked_rows(
        [(m, [float(dw.loc[m, d]) for d in dow_names]) for m in dw.index],
        dow_names, dow_colors, label="시장별 요일 매출 구성",
    )
    yak_wknd = float(dw.loc["서울약령시장", "주말비중"])
    cheong_wknd = float(dw.loc["청량리청과물시장", "주말비중"])

    # 업종별 성장·쇠퇴
    ind = pd.read_csv(DATA_PROCESSED / "industry_trend.csv", index_col=0)
    ind_show = pd.concat([ind.head(6), ind.tail(6)]).sort_values("성장률")
    fig_industry = C.diverging(
        [(i, float(r.성장률)) for i, r in ind_show.iterrows()],
        label="업종별 매출 성장률 2021→2025", unit="%",
    )
    han_growth = float(ind.loc["한의원", "성장률"]) if "한의원" in ind.index else 0
    drug_growth = float(ind.loc["의약품", "성장률"]) if "의약품" in ind.index else 0

    # 데이터 기반 재분류
    rc = pd.read_csv(DATA_PROCESSED / "market_clusters.csv", index_col=0)
    CLUSTER_NAME = {1: "주말 소매형", 2: "평일 도매형", 3: "혼합 대형", 4: "근린 생필품형"}
    rc["군집명"] = rc["군집_4"].map(CLUSTER_NAME)
    tbl_cluster = "\n".join(
        f'<tr><td>{m}</td><td class="ctr">{r.문헌축}</td>'
        f'<td class="ctr">{r.군집명}</td>'
        f'<td class="num">{float(dw.loc[m, "주말비중"]):.1f}%</td></tr>'
        for m, r in rc.sort_values("군집_4").iterrows()
    )

    # ================= 공실 데이터 신뢰성 =================
    dq = pd.read_csv(DATA_PROCESSED / "vacancy_data_quality.csv")
    dq_recent = dq[dq["구간"].str.startswith(("2017", "2018", "2019", "2020", "2021", "2022"))]
    fig_dq = C.hbar(
        [(r.구간, r._2) for r in dq_recent.itertuples()],
        label="전년도와 완전히 동일한 기록의 비율", unit="%",
        highlight={"2021→2022", "2022→2023"},
    )

    nat = pd.read_csv(DATA_PROCESSED / "vacancy_national_trend.csv")
    nat_years = [y for y in nat.year if y >= 2014]
    nat_d = dict(zip(nat.year, nat["공실률%"]))
    clu_d = dict(zip(agg.index, agg.rate))
    fig_nat = C.line(
        [("전국 평균", {y: nat_d[y] for y in nat_years}, C.SOFT),
         ("청량리 클러스터", {y: clu_d.get(y) for y in nat_years}, C.ACCENT)],
        nat_years, height=210, unit="%", label="전국 대비 클러스터 공실률",
    )

    opens = pd.read_csv(DATA_PROCESSED / "cluster_open_stores.csv", index_col=0)
    open_years = [int(c) for c in opens.columns if int(c) >= 2014]
    fig_open = C.line(
        [(m, {y: (float(opens.loc[m, str(y)]) if pd.notna(opens.loc[m, str(y)]) else None)
              for y in open_years}, c)
         for m, c in zip(["경동시장", "서울약령시장", "청량리종합시장", "청량리전통시장"],
                         ["#B03A3A", "#2E5E8A", "#8FBF9F", "#C98A5B"])],
        open_years, height=224, unit="", label="주요 시장 영업점포수 추이",
    )

    dq_last = float(dq.iloc[-1]["동일비율%"])
    dq_prev = float(dq.iloc[-2]["동일비율%"])
    nat_2017 = nat_d.get(2017, 0)
    nat_2023 = nat_d.get(2023, 0)
    kd_open_19 = int(opens.loc["경동시장", "2019"])
    kd_open_23 = int(opens.loc["경동시장", "2023"])

    yak_growth = growth.get("서울약령시장", 0)
    kd_growth = growth.get("경동시장", 0)
    yak_net = int(net.get("서울약령시장", 0))
    kd_sales_21 = ysales.loc["경동시장", 2021]
    kd_sales_25 = ysales.loc["경동시장", 2025]
    kd_youth_21 = float(a21.get("경동시장", 0))
    kd_youth_25 = float(a25.get("경동시장", 0))
    n_older = int((delta < 0).sum())

    ctx = dict(
        fig_growth=fig_growth, fig_sales_trend=fig_sales_trend, fig_time=fig_time,
        fig_age=fig_age, fig_paradox=fig_paradox, fig_net=fig_net,
        yak_growth=f"{yak_growth:.0f}", kd_growth=f"{kd_growth:.0f}",
        yak_net=f"{yak_net:+d}",
        kd_sales_21=f"{kd_sales_21:,.0f}", kd_sales_25=f"{kd_sales_25:,.0f}",
        kd_youth_21=f"{kd_youth_21:.1f}", kd_youth_25=f"{kd_youth_25:.1f}",
        n_older=str(n_older), n_golmok=str(len(growth)),
        fig_dq=fig_dq, fig_nat=fig_nat, fig_open=fig_open,
        dq_last=f"{dq_last:.1f}", dq_prev=f"{dq_prev:.1f}",
        nat_2017=f"{nat_2017:.2f}", nat_2023=f"{nat_2023:.2f}",
        kd_open_19=f"{kd_open_19:,}", kd_open_23=f"{kd_open_23:,}",
        fig_night=fig_night, fig_movein=fig_movein, fig_profile=fig_profile,
        jn_chg=f"{jn_chg:+.1f}", jg_chg=f"{jg_chg:+.1f}",
        jn_25=f"{jn_25:+.1f}", jg_25=f"{jg_25:+.1f}",
        cl_ratio=f"{cl_ratio:.2f}", jg_ratio=f"{jg_ratio:.2f}",
        n_months=str(n_months),
        fig_agepop=fig_agepop, fig_dow=fig_dow, fig_industry=fig_industry,
        tbl_cluster=tbl_cluster,
        jg60=f"{jg60:.1f}", jg60_n=f"{abs(jg60_n):,.0f}", cl60=f"{cl60:.1f}",
        yak_wknd=f"{yak_wknd:.1f}", cheong_wknd=f"{cheong_wknd:.1f}",
        han_growth=f"{han_growth:.0f}", drug_growth=f"{drug_growth:.1f}",
        cur_total=fmt(cur_total), cur_vacant=fmt(cur_vacant), cur_rate=f"{cur_rate:.1f}",
        top1_name=top1_name, top1_share=f"{top1_share:.1f}", top2_share=f"{top2_share:.1f}",
        kd_2019=f"{kd.get(2019, 0):.1f}", kd_2020=f"{kd.get(2020, 0):.1f}",
        kd_2023=f"{kd.get(2023, 0):.1f}",
        cd_2021=f"{cd.get(2021, 0):.1f}", cd_2023=f"{cd.get(2023, 0):.1f}",
        n_markets=len(master), n_merchants=fmt(master.merchants_total.sum()),
        n_stalls=fmt(master.street_stalls.sum()),
        hdr=hdr, tbl_cur=tbl_cur, tbl_pivot=tbl_pivot,
        fig_cluster=fig_cluster, fig_two=fig_two, fig_cur=fig_cur, fig_conc=fig_conc,
        fig_axis_mix=fig_axis_mix, fig_axis_rate=fig_axis_rate,
        fig_size=fig_size, fig_density=fig_density, fig_stalls=fig_stalls,
        ax=ax,
    )

    return ctx


def render(ctx, template_path, out_path):
    """«키» 자리표시자를 값으로 바꾼다. CSS 중괄호와 충돌하지 않도록 format()은 쓰지 않는다."""
    import re

    html = open(template_path, encoding="utf-8").read()
    for key, val in ctx.items():
        html = html.replace(f"«{key}»", str(val))
    missing = set(re.findall(r"«(\w+)»", html))
    if missing:
        raise SystemExit(f"치환되지 않은 자리표시자: {sorted(missing)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    render(build(), ROOT / "src" / "report_template.html", OUT)
