"""서울시 상권분석서비스 추정매출로 청량리 시장 클러스터를 분석한다.

이 데이터가 중요한 이유는 시간대·요일·연령대별 매출이 분해되어 있다는 점이다.
생활인구(체류)와 달리 실제 결제가 일어난 시점을 보므로, 4개 기능축이 정말로
서로 다른 시간대에 작동하는지 직접 검증할 수 있다.

⚠️ 2024년부터 상권 공간단위가 '표준단위구역'으로 바뀌었다. 상권코드가 유지되는지
   먼저 확인하고, 끊겼다면 2021~2023 과 2024~2025 를 따로 다뤄야 한다.

    uv run python src/analyze_golmok.py
"""

import csv
import io
import zipfile

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW, TABLES

SRC = DATA_RAW / "golmok"

# 상권코드 → (표시명, 기능축). 청량종합도매시장은 상권분석서비스에 없다.
MARKETS = {
    "3130086": ("서울약령시장", "A"),
    "3130088": ("경동시장", "A"),
    "3130087": ("경동광성상가", "A"),
    "3130094": ("청량리청과물시장", "B"),
    "3130093": ("동서시장", "B"),
    "3130090": ("청량리종합시장", "C"),
    "3130092": ("청량리농수산물시장", "C"),
    "3130089": ("청량리수산시장", "C"),
    "3130095": ("청량리전통시장", "D"),
}
REFERENCE = {"3120063": ("청량리역 발달상권", "R")}  # 비교용 기준선

TIME_BANDS = ["00~06", "06~11", "11~14", "14~17", "17~21", "21~24"]
AGES = ["10", "20", "30", "40", "50", "60_이상"]


def read_year(year: int) -> pd.DataFrame:
    """한 해치 ZIP에서 대상 상권 행만 뽑는다. 전국이 아니라 서울이라 크지 않다."""
    path = SRC / f"추정매출_{year}.zip"
    wanted = {**MARKETS, **REFERENCE}
    rows = []
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as fh:
            reader = csv.reader(io.TextIOWrapper(fh, encoding="cp949", errors="replace"))
            hdr = next(reader)
            idx = {c: i for i, c in enumerate(hdr)}
            i_cd = idx["상권_코드"]
            for row in reader:
                if len(row) <= i_cd or row[i_cd] not in wanted:
                    continue
                rows.append(row)
    df = pd.DataFrame(rows, columns=hdr)
    num = [c for c in hdr if "금액" in c or "건수" in c]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce").fillna(0)
    df["year"] = year
    return df


def main():
    years = [2021, 2022, 2023, 2024, 2025]
    df = pd.concat([read_year(y) for y in years], ignore_index=True)

    df["market"] = df["상권_코드"].map(lambda c: {**MARKETS, **REFERENCE}[c][0])
    df["axis"] = df["상권_코드"].map(lambda c: {**MARKETS, **REFERENCE}[c][1])
    df["quarter"] = df["기준_년분기_코드"].astype(str)

    # 상권코드 연속성 확인 — 2024년 체계 변경의 영향을 실제로 받았는지
    per_year = df.groupby("year")["상권_코드"].nunique()
    print("=== 연도별 매칭된 상권 수 (총 10개 기대) ===")
    print(per_year.to_string())
    if per_year.min() < len(MARKETS):
        print("⚠️ 일부 연도에 상권이 누락됨 — 2024년 표준단위구역 전환 영향 가능")
    print()

    mk = df[df.axis != "R"]

    # ---- 1) 시간대별 매출 구성비 (기능축 검증) ----
    tcols = [f"시간대_{b}_매출_금액" for b in TIME_BANDS]
    t = mk[mk.year == 2023].groupby(["axis", "market"])[tcols].sum()
    tp = t.div(t.sum(axis=1), axis=0) * 100
    tp.columns = TIME_BANDS
    print("=== 2023년 시간대별 매출 구성비 (%) ===")
    print(tp.round(1).to_string())
    print()

    axis_t = mk[mk.year == 2023].groupby("axis")[tcols].sum()
    axis_tp = (axis_t.div(axis_t.sum(axis=1), axis=0) * 100)
    axis_tp.columns = TIME_BANDS

    # ---- 2) 시장별 분기 매출 추이 ----
    q = mk.groupby(["market", "quarter"])["당월_매출_금액"].sum().reset_index()
    q["매출_억"] = q.당월_매출_금액 / 1e8

    # ---- 3) 연령대 구성 (연도별로 남겨 변화를 볼 수 있게) ----
    acols = [f"연령대_{a}_매출_금액" for a in AGES]
    age_rows = []
    for yr in years:
        g = mk[mk.year == yr].groupby("market")[acols].sum()
        p = (g.div(g.sum(axis=1), axis=0) * 100)
        p.columns = ["10대", "20대", "30대", "40대", "50대", "60대+"]
        p["year"] = yr
        age_rows.append(p.reset_index())
    age_all = pd.concat(age_rows, ignore_index=True)
    age_all["청년층"] = age_all["20대"] + age_all["30대"]  # 20~30대 합
    age_all.round(2).to_csv(DATA_PROCESSED / "golmok_age_by_year.csv", index=False)

    ap = age_all[age_all.year == 2023].set_index("market")[
        ["10대", "20대", "30대", "40대", "50대", "60대+"]]

    # ---- 4) 경동시장 스타벅스 전후 (2022Q4 개점) ----
    kd = q[q.market == "경동시장"].sort_values("quarter")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    tp.round(2).to_csv(DATA_PROCESSED / "golmok_time_profile.csv")
    axis_tp.round(2).to_csv(DATA_PROCESSED / "golmok_time_profile_axis.csv")
    q.to_csv(DATA_PROCESSED / "golmok_quarterly_sales.csv", index=False)
    ap.round(2).to_csv(DATA_PROCESSED / "golmok_age_mix.csv")

    print("=== 2023년 연령대별 매출 구성비 (%) ===")
    print(ap.round(1).to_string())
    print()
    print("=== 경동시장 분기 매출 (억원) ===")
    print(kd[["quarter", "매출_억"]].round(1).to_string(index=False))

    print(f"\n저장: {DATA_PROCESSED}/golmok_*.csv")


if __name__ == "__main__":
    main()
