"""추가 분석 4종.

  1) 배후인구의 연령 구성 변화 — 인구가 줄었다면 '누가' 줄었는지
  2) 요일별 매출 패턴 — 도매(평일 편중)와 소매(주말 분산)를 가른다
  3) 업종별 매출 성장·쇠퇴 — 지원 대상 업종을 고르기 위한 근거
  4) 데이터 기반 시장 유형 재분류 — 문헌으로 세운 4개 축을 실제 거래 패턴으로 다시 만든다

4번이 중요한 이유: 앞서 B축(새벽 청과 도매) 가설이 카드매출로 기각되었다.
문헌이 아니라 데이터가 유형을 정하게 하면 그런 오류를 피할 수 있다.

    uv run python src/analyze_extra.py
"""

import numpy as np
import pandas as pd

from analyze_golmok import AGES, MARKETS, TIME_BANDS, read_year
from config import DATA_PROCESSED

DOW = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def age_shift() -> pd.DataFrame:
    """행정동별 야간인구를 연령대로 쪼개 2022년 대비 2025년 변화를 본다."""
    age = pd.read_csv(DATA_PROCESSED / "local_people_age.csv", dtype={"ym": str})
    night = age[age.phase == "야간"].copy()
    night["year"] = night.ym.str[:4].astype(int)
    bands = ["0-19", "20-39", "40-59", "60+"]

    y = night.groupby(["dong", "year"])[bands].mean()
    out = []
    for dong in night.dong.unique():
        if (dong, 2022) not in y.index or (dong, 2025) not in y.index:
            continue
        a, b = y.loc[(dong, 2022)], y.loc[(dong, 2025)]
        row = {"dong": dong}
        for band in bands:
            row[f"{band}_2022"] = a[band]
            row[f"{band}_2025"] = b[band]
            row[f"{band}_변화율"] = (b[band] / a[band] - 1) * 100 if a[band] else np.nan
        out.append(row)
    return pd.DataFrame(out)


def load_sales(years) -> pd.DataFrame:
    df = pd.concat([read_year(y) for y in years], ignore_index=True)
    df = df[df["상권_코드"].isin(MARKETS)].copy()
    df["market"] = df["상권_코드"].map(lambda c: MARKETS[c][0])
    df["axis"] = df["상권_코드"].map(lambda c: MARKETS[c][1])
    df["year"] = df["기준_년분기_코드"].astype(str).str[:4].astype(int)
    return df


def dow_profile(df) -> pd.DataFrame:
    """요일별 매출 구성비. 주말 비중이 낮을수록 도매 성격이 강하다."""
    cols = [f"{d}_매출_금액" for d in DOW]
    g = df[df.year == 2025].groupby("market")[cols].sum()
    p = g.div(g.sum(axis=1), axis=0) * 100
    p.columns = DOW
    p["주말비중"] = p["토요일"] + p["일요일"]
    return p


def industry_trend(df) -> pd.DataFrame:
    """업종별 매출 2021→2025. 클러스터 전체 합산 기준."""
    g = df.groupby(["서비스_업종_코드_명", "year"])["당월_매출_금액"].sum().unstack()
    g = g[[c for c in (2021, 2025) if c in g.columns]].dropna()
    g = g[g[2021] > 5e8]  # 연 5억 미만 업종은 변동이 커서 제외
    out = pd.DataFrame({
        "매출_2021억": g[2021] / 1e8,
        "매출_2025억": g[2025] / 1e8,
        "성장률": (g[2025] / g[2021] - 1) * 100,
    })
    return out.sort_values("성장률", ascending=False)


def reclassify(df) -> pd.DataFrame:
    """시간대·요일·연령 프로파일로 시장을 다시 묶는다.

    각 시장을 (시간대 6 + 요일 7 + 연령 6) = 19차원 구성비 벡터로 만든 뒤
    계층적 군집화한다. 구성비라 시장 규모의 영향을 받지 않는다.
    """
    from scipy.cluster.hierarchy import fcluster, linkage

    cur = df[df.year == 2025]
    tcols = [f"시간대_{b}_매출_금액" for b in TIME_BANDS]
    dcols = [f"{d}_매출_금액" for d in DOW]
    acols = [f"연령대_{a}_매출_금액" for a in AGES]

    parts = []
    for cols in (tcols, dcols, acols):
        g = cur.groupby("market")[cols].sum()
        parts.append(g.div(g.sum(axis=1), axis=0))
    X = pd.concat(parts, axis=1).fillna(0)

    Z = linkage(X.values, method="ward")
    for k in (3, 4):
        X[f"군집_{k}"] = fcluster(Z, k, criterion="maxclust")
    X["문헌축"] = [MARKETS[c][1] for c in
                 [next(k for k, v in MARKETS.items() if v[0] == m) for m in X.index]]
    return X


def main():
    print("=== ① 배후인구 연령 구성 변화 (야간, 2022→2025) ===")
    a = age_shift().set_index("dong")
    cols = [c for c in a.columns if c.endswith("변화율")]
    focus = a.loc[["제기동", "청량리동", "용신동", "전농1동"], cols]
    focus.columns = [c.replace("_변화율", "") for c in focus.columns]
    print(focus.round(1).to_string(), "\n")

    df = load_sales([2021, 2025])

    print("=== ② 요일별 매출 구성 (2025년, %) ===")
    d = dow_profile(df).sort_values("주말비중")
    print(d.round(1).to_string(), "\n")

    print("=== ③ 업종별 매출 성장률 (2021→2025) ===")
    ind = industry_trend(df)
    print("상위 8:")
    print(ind.head(8).round(1).to_string())
    print("\n하위 8:")
    print(ind.tail(8).round(1).to_string(), "\n")

    print("=== ④ 데이터 기반 시장 유형 재분류 ===")
    rc = reclassify(df)
    print(rc[["문헌축", "군집_3", "군집_4"]].sort_values("군집_4").to_string(), "\n")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    a.to_csv(DATA_PROCESSED / "pop_age_shift.csv")
    d.to_csv(DATA_PROCESSED / "sales_dow.csv")
    ind.to_csv(DATA_PROCESSED / "industry_trend.csv")
    rc.to_csv(DATA_PROCESSED / "market_clusters.csv")
    print(f"저장: {DATA_PROCESSED}/pop_age_shift.csv 외 3건")


if __name__ == "__main__":
    main()
