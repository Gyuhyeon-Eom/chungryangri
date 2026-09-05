"""복합 분석 4종.

지금까지의 분석은 변수를 하나씩 따로 봤다. 여기서는 변수 간 관계를 본다.

  1) 서울 전체 전통시장 벤치마크 — 청량리는 서울 평균 대비 어디에 있는가
  2) 변이-할당 분석(shift-share) — 부진의 원인이 업종 구성인가 자체 경쟁력인가
  3) 매출 분해 — 매출 변화가 거래 건수 때문인가 객단가 때문인가
  4) 배후인구-매출 탄력성 — 인구 1% 변화가 매출을 몇 % 움직이는가 (고정효과 패널)

2번이 특히 중요하다. 서울약령시장의 부진을 두고 '한방 수요 축소 탓'이라고
했는데, 그것이 전부인지 아니면 같은 업종 안에서도 유독 못하는 것인지는
업종 구성 효과와 경쟁력 효과를 분리해야 답할 수 있다.

    uv run python src/analyze_advanced.py
"""

import csv
import io
import zipfile

import numpy as np
import pandas as pd

from config import DATA_PROCESSED, DATA_RAW
from analyze_golmok import MARKETS

SRC = DATA_RAW / "golmok"

# 시장 → 소재 행정동 (배후인구 매칭용)
MARKET_DONG = {
    "경동시장": "제기동", "서울약령시장": "제기동", "경동광성상가": "제기동",
    "청량리종합시장": "청량리동", "청량리청과물시장": "청량리동", "동서시장": "청량리동",
    "청량리전통시장": "청량리동", "청량리농수산물시장": "청량리동",
    "청량리수산시장": "용신동",
}


def read_all_markets(year: int) -> pd.DataFrame:
    """서울 전체 '전통시장' 상권의 업종별 매출을 읽는다."""
    path = SRC / f"추정매출_{year}.zip"
    rows = []
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as fh:
            r = csv.reader(io.TextIOWrapper(fh, encoding="cp949", errors="replace"))
            hdr = next(r)
            i_se, i_cd, i_nm = (hdr.index(c) for c in
                                ("상권_구분_코드_명", "상권_코드", "상권_코드_명"))
            i_ind = hdr.index("서비스_업종_코드_명")
            i_amt, i_cnt = hdr.index("당월_매출_금액"), hdr.index("당월_매출_건수")
            for row in r:
                if len(row) <= i_cnt or row[i_se] != "전통시장":
                    continue
                rows.append((row[i_cd], row[i_nm], row[i_ind],
                             pd.to_numeric(row[i_amt], errors="coerce"),
                             pd.to_numeric(row[i_cnt], errors="coerce")))
    df = pd.DataFrame(rows, columns=["code", "name", "industry", "amt", "cnt"]).fillna(0)
    df["year"] = year
    return df


def benchmark(d21, d25) -> pd.DataFrame:
    """서울 283개 전통시장 상권의 성장률 분포에서 청량리 9개의 위치."""
    a = d21.groupby(["code", "name"])["amt"].sum()
    b = d25.groupby(["code", "name"])["amt"].sum()
    j = pd.concat([a.rename("y21"), b.rename("y25")], axis=1).dropna()
    j = j[j.y21 > 1e8]
    j["growth"] = (j.y25 / j.y21 - 1) * 100
    j = j.reset_index()
    j["청량리"] = j.code.isin(MARKETS)
    j["백분위"] = j.growth.rank(pct=True) * 100
    return j


def shift_share(d21, d25) -> pd.DataFrame:
    """변이-할당 분석.

    시장 i의 매출 변화를 세 성분으로 나눈다.
      전체효과(SE) : 서울 전통시장 전체가 성장한 만큼 = S0 × g_all
      업종구성효과(IM): 보유 업종의 서울 전체 성장이 평균과 다른 만큼 = S0 × (g_j − g_all)
      경쟁력효과(CE): 같은 업종인데 이 시장만 다른 만큼 = S0 × (g_ij − g_j)
    """
    all21, all25 = d21.amt.sum(), d25.amt.sum()
    g_all = all25 / all21 - 1

    ind21 = d21.groupby("industry")["amt"].sum()
    ind25 = d25.groupby("industry")["amt"].sum()
    g_ind = (ind25 / ind21 - 1).replace([np.inf, -np.inf], np.nan)

    a = d21[d21.code.isin(MARKETS)].groupby(["code", "industry"])["amt"].sum()
    b = d25[d25.code.isin(MARKETS)].groupby(["code", "industry"])["amt"].sum()
    j = pd.concat([a.rename("s0"), b.rename("s1")], axis=1).fillna(0)
    j = j[j.s0 > 0].reset_index()
    j["g_ij"] = j.s1 / j.s0 - 1
    j["g_j"] = j.industry.map(g_ind)
    j = j.dropna(subset=["g_j"])

    j["SE"] = j.s0 * g_all
    j["IM"] = j.s0 * (j.g_j - g_all)
    j["CE"] = j.s0 * (j.g_ij - j.g_j)

    out = j.groupby("code")[["s0", "s1", "SE", "IM", "CE"]].sum()
    out["실제증감"] = out.s1 - out.s0
    out["market"] = [MARKETS[c][0] for c in out.index]
    for c in ("SE", "IM", "CE", "실제증감"):
        out[c + "_억"] = out[c] / 1e8
    out["IM_기여%"] = out.IM / out.s0 * 100
    out["CE_기여%"] = out.CE / out.s0 * 100
    return out.set_index("market").sort_values("CE_기여%")


def decompose_ticket(d21, d25) -> pd.DataFrame:
    """매출 = 건수 × 객단가. 어느 쪽이 움직였는지 본다."""
    a = d21[d21.code.isin(MARKETS)].groupby("code")[["amt", "cnt"]].sum()
    b = d25[d25.code.isin(MARKETS)].groupby("code")[["amt", "cnt"]].sum()
    j = pd.concat([a.add_suffix("21"), b.add_suffix("25")], axis=1)
    j["market"] = [MARKETS[c][0] for c in j.index]
    j["객단가21"] = j.amt21 / j.cnt21
    j["객단가25"] = j.amt25 / j.cnt25
    j["매출증가%"] = (j.amt25 / j.amt21 - 1) * 100
    j["건수증가%"] = (j.cnt25 / j.cnt21 - 1) * 100
    j["객단가증가%"] = (j.객단가25 / j.객단가21 - 1) * 100
    return j.set_index("market")[["매출증가%", "건수증가%", "객단가증가%", "객단가21", "객단가25"]]


def elasticity() -> tuple[pd.DataFrame, float, float]:
    """배후인구와 매출의 관계를 고정효과 패널로 추정한다.

    log(매출) = α_i + β·log(배후인구) + ε
    시장별 평균을 빼는(within) 변환으로 시장 고유 특성을 제거하므로,
    '시장 규모가 커서 매출도 크다'는 상관이 아니라 '같은 시장 안에서
    인구가 움직일 때 매출이 얼마나 따라 움직이는가'를 본다.
    """
    q = pd.read_csv(DATA_PROCESSED / "golmok_quarterly_sales.csv", dtype={"quarter": str})
    q["dong"] = q.market.map(MARKET_DONG)
    q = q.dropna(subset=["dong"])

    lp = pd.read_csv(DATA_PROCESSED / "local_people_hourly.csv", dtype={"ym": str})
    night = lp[lp.hour.between(3, 5)].groupby(["ym", "dong"])["pop"].mean().reset_index()
    night["quarter"] = night.ym.str[:4] + ((night.ym.str[4:].astype(int) - 1) // 3 + 1).astype(str)
    pop = night.groupby(["quarter", "dong"])["pop"].mean().reset_index()

    m = q.merge(pop, on=["quarter", "dong"], how="inner")
    m = m[(m.당월_매출_금액 > 0) & (m["pop"] > 0)].copy()
    m["ly"] = np.log(m.당월_매출_금액)
    m["lp"] = np.log(m["pop"])

    # within 변환 (시장 고정효과)
    m["ly_d"] = m.ly - m.groupby("market").ly.transform("mean")
    m["lp_d"] = m.lp - m.groupby("market").lp.transform("mean")

    x, y = m.lp_d.values, m.ly_d.values
    beta = (x @ y) / (x @ x)
    resid = y - beta * x
    n, k = len(y), m.market.nunique() + 1
    se = np.sqrt((resid @ resid) / (n - k) / (x @ x))
    return m, beta, beta / se


def main():
    d21, d25 = read_all_markets(2021), read_all_markets(2025)
    print(f"서울 전통시장 상권 {d25.code.nunique()}개 · 업종 {d25.industry.nunique()}개\n")

    print("=== ① 서울 전체 전통시장 대비 위치 ===")
    bm = benchmark(d21, d25)
    seoul_med = bm[~bm.청량리].growth.median()
    print(f"서울 전통시장 중위 성장률: {seoul_med:.1f}%")
    print(bm[bm.청량리][["name", "growth", "백분위"]]
          .sort_values("growth", ascending=False).round(1).to_string(index=False), "\n")

    print("=== ② 변이-할당 분석 (억원) ===")
    ss = shift_share(d21, d25)
    print(ss[["SE_억", "IM_억", "CE_억", "실제증감_억", "IM_기여%", "CE_기여%"]]
          .round(1).to_string(), "\n")

    print("=== ③ 매출 = 건수 × 객단가 분해 (%) ===")
    dt = decompose_ticket(d21, d25)
    print(dt.round(1).to_string(), "\n")

    print("=== ④ 배후인구-매출 탄력성 (시장 고정효과) ===")
    panel, beta, t = elasticity()
    print(f"관측치 {len(panel)}개 · 시장 {panel.market.nunique()}개 · 분기 {panel.quarter.nunique()}개")
    print(f"탄력성 β = {beta:.2f}  (t = {t:.2f})")
    print(f"→ 배후인구 1% 감소 시 매출 {abs(beta):.2f}% 변동\n")

    bm.to_csv(DATA_PROCESSED / "seoul_benchmark.csv", index=False)
    ss.to_csv(DATA_PROCESSED / "shift_share.csv")
    dt.to_csv(DATA_PROCESSED / "ticket_decomp.csv")
    pd.DataFrame([{"beta": beta, "t": t, "n": len(panel),
                   "seoul_median": seoul_med}]).to_csv(
        DATA_PROCESSED / "elasticity.csv", index=False)
    print(f"저장: {DATA_PROCESSED}/seoul_benchmark.csv 외 3건")


if __name__ == "__main__":
    main()
