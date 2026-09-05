"""연도별 전통시장 영업점포·빈점포 현황(2006~2023)에서 청량리 클러스터 시계열을 만든다.

출처: data.go.kr 15143951 — 연도별로 CSV가 한 개씩 들어있는 ZIP.
시장명 표기가 연도마다 흔들려(띄어쓰기, '서울'/'서울시' 등) 정규화 후 매칭한다.
"""

import re
from pathlib import Path

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW, TABLES

SRC = DATA_RAW / "data_go_kr" / "vacancy"

# 마스터의 정규화 시장명 → 표시명
TARGETS = {
    "서울약령시장": "서울약령시장",
    "경동시장": "경동시장",
    "청량리청과물시장": "청량리청과물시장",
    "경동광성상가": "경동광성상가",
    "청량리농수산물시장": "청량리농수산물시장",
    "청량리종합시장": "청량리종합시장",
    "동서시장": "동서시장",
    "청량리수산시장": "청량리수산시장",
    "청량종합도매시장": "청량종합도매시장",
    "청량리전통시장": "청량리전통시장",
}


def normalize(name: str) -> str:
    return re.sub(r"\s+", "", str(name)).strip()


def read_korean_csv(path: Path) -> pd.DataFrame:
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(path)


def main():
    files = sorted(SRC.rglob("*.csv"))
    if not files:
        raise SystemExit(f"CSV를 찾지 못했습니다: {SRC}")

    rows = []
    for path in files:
        year = int(re.search(r"\((\d{4})년\)", path.name).group(1))
        df = read_korean_csv(path)
        df.columns = [c.strip() for c in df.columns]

        open_col = next(c for c in df.columns if "영업점포" in c)
        vac_col = next(c for c in df.columns if "빈점포" in c)
        addr_col = next((c for c in df.columns if "주소" in c), None)

        df["_key"] = df["시장명"].map(normalize)
        # 동명이시장이 전국에 있으므로 주소로 동대문구를 한 번 더 거른다
        if addr_col:
            df = df[df[addr_col].astype(str).str.contains("동대문", na=False)]

        hit = df[df["_key"].isin(TARGETS)]
        for _, r in hit.iterrows():
            rows.append({
                "year": year,
                "market": TARGETS[r["_key"]],
                "open": pd.to_numeric(r[open_col], errors="coerce"),
                "vacant": pd.to_numeric(r[vac_col], errors="coerce"),
            })

    ts = pd.DataFrame(rows)
    ts["total"] = ts["open"] + ts["vacant"]
    ts["vacancy_rate"] = (ts.vacant / ts.total * 100).round(1)
    ts = ts.sort_values(["market", "year"])

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    ts.to_csv(DATA_PROCESSED / "vacancy_timeseries.csv", index=False)
    TABLES.mkdir(parents=True, exist_ok=True)

    years = sorted(ts.year.unique())
    print(f"연도 범위: {years[0]} ~ {years[-1]} ({len(years)}개 연도)")
    print(f"매칭 시장: {ts.market.nunique()}개\n")

    print("=== 시장별 공실률(%) 추이 ===")
    pivot = ts.pivot_table(index="market", columns="year", values="vacancy_rate")
    print(pivot.to_string(na_rep="—"))

    print("\n=== 클러스터 합계 ===")
    agg = ts.groupby("year").agg(전체=("total", "sum"), 공실=("vacant", "sum"))
    agg["공실률%"] = (agg.공실 / agg.전체 * 100).round(1)
    print(agg.to_string())

    pivot.to_csv(TABLES / "vacancy_rate_by_year.csv")
    agg.to_csv(TABLES / "vacancy_cluster_by_year.csv")


if __name__ == "__main__":
    main()
