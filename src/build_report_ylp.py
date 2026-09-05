"""회사소개서 첨부용 보고서 생성.

정책 보고서(build_report.py)와 같은 분석 결과를 쓰되, 목적이 다르다.
읽는 사람이 발주처·협력사이므로 '무엇을 발견했는가'만큼 '어떻게 발견했는가'가 중요하다.
따라서 (a) 처리 규모와 방법론을 앞에 세우고, (b) 발견을 Pain Point 단위로 재배열하며,
(c) 공공데이터 결함 검증을 뒤에 묻지 않고 독립 장으로 드러낸다.

    uv run python src/build_report_ylp.py
"""

import pandas as pd

import charts as C
from build_report import ROOT, build, render
from config import DATA_INTERIM, DATA_PROCESSED

OUT = ROOT / "output" / "report_ylp.html"
DOW = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
BANDS = ["00~06", "06~11", "11~14", "14~17", "17~21", "21~24"]


def extra_context() -> dict:
    """정책 보고서에 없는, 규모·방법론을 보여주기 위한 시각화."""
    ctx = {}

    # --- 처리 규모 타일 ---
    n_months = len(list((DATA_INTERIM / "local_people_ddm").glob("*.csv")))
    ctx["fig_scale"] = C.stat_tiles([
        ("54.3", "M행", "생활인구 원시 레코드"),
        (str(n_months), "개월", "시계열 (2017~2026)"),
        ("138", "GB", "원본 다운로드 용량"),
        ("1,812", "개", "전국 시장 교차검증"),
        ("9", "개", "분석 대상 시장"),
        ("20", "분기", "카드매출 시계열"),
        ("43", "개", "업종 분류"),
        ("19", "차원", "군집분석 특성벡터"),
    ], cols=4, label="분석 처리 규모")
    ctx["n_months_lp"] = str(n_months)

    # --- 시간대 × 시장 히트맵 ---
    tp = pd.read_csv(DATA_PROCESSED / "golmok_time_profile.csv").sort_values("axis")
    ctx["fig_time_heat"] = C.heatmap(
        list(tp.market), BANDS,
        [[float(r[b]) for b in BANDS] for _, r in tp.iterrows()],
        label="시장 × 시간대 매출 구성비", unit="%",
    )

    # --- 요일 × 시장 히트맵 ---
    dw = pd.read_csv(DATA_PROCESSED / "sales_dow.csv", index_col=0).sort_values("주말비중")
    ctx["fig_dow_heat"] = C.heatmap(
        list(dw.index), ["월", "화", "수", "목", "금", "토", "일"],
        [[float(dw.loc[m, d]) for d in DOW] for m in dw.index],
        label="시장 × 요일 매출 구성비", unit="%",
    )

    # --- 연령대 × 시장 히트맵 ---
    age = pd.read_csv(DATA_PROCESSED / "golmok_age_by_year.csv")
    a25 = age[age.year == 2025].set_index("market")
    acols = ["20대", "30대", "40대", "50대", "60대+"]
    a25 = a25.sort_values("60대+")
    ctx["fig_age_heat"] = C.heatmap(
        list(a25.index), acols,
        [[float(a25.loc[m, c]) for c in acols] for m in a25.index],
        label="시장 × 연령대 매출 구성비", unit="%",
    )

    # --- 규모 대비 성장 (버블 대용 산점도) ---
    q = pd.read_csv(DATA_PROCESSED / "golmok_quarterly_sales.csv", dtype={"quarter": str})
    q["year"] = q.quarter.str[:4].astype(int)
    ys = q.groupby(["market", "year"])["당월_매출_금액"].sum().unstack() / 1e8
    growth = (ys[2025] / ys[2021] - 1) * 100
    pts = [(m, float(ys.loc[m, 2025]), float(growth[m]),
            C.WARN if growth[m] < 0 else C.ACCENT) for m in ys.index]
    ctx["fig_scale_growth"] = C.scatter(
        pts, label="매출 규모와 성장률", xlab="2025년 매출 (억원)",
        ylab="2021→2025 성장률 (%)", xunit="", yunit="%", quadrant=(0, 0), height=250,
    )

    # --- 배후인구 월별 (촘촘한 시계열) ---
    lp = pd.read_csv(DATA_PROCESSED / "local_people_hourly.csv", dtype={"ym": str})
    night = lp[lp.hour.between(3, 5)].groupby(["ym", "dong"])["pop"].mean().unstack()
    night = night.sort_index()
    # 연·분기 단위로 줄여 x축이 뭉개지지 않게 한다
    night["q"] = [f"{i[:4]}.{(int(i[4:])-1)//3+1}" for i in night.index]
    qn = night.groupby("q").mean(numeric_only=True)
    qs = [q for q in qn.index if q >= "2021"]
    xs = list(range(len(qs)))
    ctx["fig_night_q"] = C.line(
        [(d, {i: float(qn.loc[q, d]) for i, q in enumerate(qs)}, c)
         for d, c in zip(["전농1동", "용신동", "제기동", "청량리동"],
                         ["#5B8C6E", "#5B9BBF", "#B03A3A", "#C98A5B"])],
        xs, height=224, unit="", label="분기별 야간 생활인구",
    )
    ctx["q_first"], ctx["q_last"] = qs[0], qs[-1]

    # --- 업종 상위 구성 (시장별) ---
    ind = pd.read_csv(DATA_PROCESSED / "industry_trend.csv", index_col=0)
    ctx["n_industry"] = str(len(ind))

    return ctx


def main():
    ctx = build()          # 정책 보고서와 동일한 분석 결과
    ctx.update(extra_context())
    render(ctx, ROOT / "src" / "report_ylp_template.html", OUT)
    print(f"  추가 시각화 7종 (히트맵 3 · 타일 1 · 산점도 1 · 시계열 1)")


if __name__ == "__main__":
    main()
