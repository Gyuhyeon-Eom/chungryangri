"""서울 전역으로 표본을 넓힌 배후인구-매출 탄력성 추정.

앞선 추정은 청량리 9개 시장 × 20분기 = 180개 관측치였고,
95% 신뢰구간이 [0.09, 1.83]로 넓어 크기를 특정할 수 없었다.
서울 전통시장 283개로 넓히면 관측치가 5천 개대가 되어 정밀도가 올라간다.

상권과 행정동은 상권 경계 SHP의 ADSTRD_CD로 연결한다.

    uv run python src/analyze_elasticity_seoul.py
"""

import csv
import io
import re
import zipfile
from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd

from analyze_advanced import read_all_markets
from analyze_golmok import MARKETS
from config import DATA_PROCESSED, DATA_RAW

POP_DIR = DATA_RAW / "dong_pop"
SHP = DATA_RAW / "golmok" / "shp" / "trade_area.shp"

I_DATE, I_HOUR, I_DONG, I_TOT = 0, 1, 2, 3
NIGHT = {"03", "04", "05"}   # 상주인구 대리 시간대


def read_pop() -> pd.DataFrame:
    """행정동 × 분기 야간 생활인구. 파일이 커서 한 줄씩 흘리며 합산한다."""
    acc = defaultdict(lambda: [0.0, 0])   # (분기, 동) -> [합, 관측수]

    for path in sorted(POP_DIR.glob("*.zip")):
        with zipfile.ZipFile(path) as z:
            for member in [n for n in z.namelist() if n.lower().endswith(".csv")]:
                with z.open(member) as fh:
                    r = csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
                    next(r, None)
                    for row in r:
                        if len(row) <= I_TOT or row[I_HOUR] not in NIGHT:
                            continue
                        d = row[I_DATE]
                        q = f"{d[:4]}{(int(d[4:6]) - 1) // 3 + 1}"
                        try:
                            v = float(row[I_TOT])
                        except ValueError:
                            continue
                        cell = acc[(q, row[I_DONG])]
                        cell[0] += v
                        cell[1] += 1
        print(f"  {path.name} 처리", flush=True)

    rows = [{"quarter": q, "dong_cd": d, "pop": s / n}
            for (q, d), (s, n) in acc.items() if n]
    return pd.DataFrame(rows)


def main():
    print("행정동 생활인구 집계")
    pop = read_pop()
    print(f"\n행정동 {pop.dong_cd.nunique()}개 · 분기 {pop.quarter.nunique()}개 "
          f"· 관측 {len(pop):,}\n")

    # 상권 → 행정동 매핑
    areas = gpd.read_file(SHP)
    areas = areas[areas.TRDAR_SE_C == "R"][["TRDAR_CD", "TRDAR_CD_N", "ADSTRD_CD"]]
    areas.columns = ["code", "name", "dong_cd"]
    print(f"전통시장 상권 {len(areas)}개\n")

    # 상권 × 분기 매출
    sales = []
    for y in range(2021, 2026):
        d = read_all_markets(y)
        sales.append(d.groupby("code")["amt"].sum().rename(y))
    # read_all_markets 는 연 단위 합계라 분기 정보가 없다 → 원본에서 분기로 다시 읽는다
    q_rows = []
    for y in range(2021, 2026):
        path = DATA_RAW / "golmok" / f"추정매출_{y}.zip"
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(name) as fh:
                r = csv.reader(io.TextIOWrapper(fh, encoding="cp949", errors="replace"))
                hdr = next(r)
                i_se = hdr.index("상권_구분_코드_명")
                i_q, i_cd = hdr.index("기준_년분기_코드"), hdr.index("상권_코드")
                i_amt = hdr.index("당월_매출_금액")
                agg = defaultdict(float)
                for row in r:
                    if len(row) <= i_amt or row[i_se] != "전통시장":
                        continue
                    try:
                        agg[(row[i_q], row[i_cd])] += float(row[i_amt])
                    except ValueError:
                        pass
                q_rows += [{"quarter": q, "code": c, "amt": v} for (q, c), v in agg.items()]
    qs = pd.DataFrame(q_rows)

    m = qs.merge(areas, on="code").merge(pop, on=["quarter", "dong_cd"], how="inner")
    m = m[(m.amt > 0) & (m["pop"] > 0)].copy()
    m["ly"], m["lp"] = np.log(m.amt), np.log(m["pop"])
    m["ly_d"] = m.ly - m.groupby("code").ly.transform("mean")
    m["lp_d"] = m.lp - m.groupby("code").lp.transform("mean")

    x, y = m.lp_d.values, m.ly_d.values
    beta = (x @ y) / (x @ x)
    resid = y - beta * x
    n, k = len(y), m.code.nunique() + 1
    se = np.sqrt((resid @ resid) / (n - k) / (x @ x))
    t = beta / se
    r2 = 1 - (resid @ resid) / (y @ y)

    print("=== 서울 전체 전통시장 패널 ===")
    print(f"상권 {m.code.nunique()}개 · 분기 {m.quarter.nunique()}개 · 관측치 {n:,}개")
    print(f"β = {beta:.3f}  SE = {se:.3f}  t = {t:.2f}")
    print(f"95% 신뢰구간 = [{beta-1.96*se:.2f}, {beta+1.96*se:.2f}]")
    print(f"within R² = {r2:.3f}\n")

    # 청량리만 따로
    sub = m[m.code.isin(MARKETS)]
    xs, ys = sub.lp_d.values, sub.ly_d.values
    b2 = (xs @ ys) / (xs @ xs)
    print(f"참고 · 청량리 9개만: 관측치 {len(sub)}개, β = {b2:.2f}")

    pd.DataFrame([{"beta": beta, "se": se, "t": t, "n": n,
                   "ci_lo": beta - 1.96 * se, "ci_hi": beta + 1.96 * se,
                   "r2": r2, "n_area": m.code.nunique()}]).to_csv(
        DATA_PROCESSED / "elasticity_seoul.csv", index=False)
    print(f"\n저장: {DATA_PROCESSED}/elasticity_seoul.csv")


if __name__ == "__main__":
    main()
