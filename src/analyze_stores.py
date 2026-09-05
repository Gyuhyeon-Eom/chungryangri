"""상권분석서비스 점포 데이터로 청량리 시장의 개·폐업 회전을 본다.

⚠️ 2024년부터 CSV 컬럼명이 한글에서 영문으로 바뀌었다(표준단위구역 전환).
   컬럼을 정규화하지 않으면 2024~2025년이 통째로 누락된다.

    uv run python src/analyze_stores.py
"""

import csv
import io
import zipfile

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW
from analyze_golmok import MARKETS

SRC = DATA_RAW / "golmok"

# 영문(2024~) → 한글(~2023) 컬럼 대응
RENAME = {
    "stdr_yyqu_cd": "기준_년분기_코드",
    "trdar_cd": "상권_코드",
    "trdar_cd_nm": "상권_코드_명",
    "svc_induty_cd_nm": "서비스_업종_코드_명",
    "stor_co": "점포_수",
    "opbiz_stor_co": "개업_점포_수",
    "clsbiz_stor_co": "폐업_점포_수",
    "opbiz_rt": "개업_율",
    "clsbiz_rt": "폐업_률",
}
NEED = ["기준_년분기_코드", "상권_코드", "서비스_업종_코드_명",
        "점포_수", "개업_점포_수", "폐업_점포_수"]


def read_year(year: int) -> pd.DataFrame:
    path = SRC / f"점포_{year}.zip"
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as fh:
            reader = csv.reader(io.TextIOWrapper(fh, encoding="cp949", errors="replace"))
            hdr = [RENAME.get(c, c) for c in next(reader)]
            i_cd = hdr.index("상권_코드")
            rows = [r for r in reader if len(r) > i_cd and r[i_cd] in MARKETS]

    df = pd.DataFrame(rows, columns=hdr)
    missing = [c for c in NEED if c not in df.columns]
    if missing:
        raise ValueError(f"{year}년 파일에 없는 컬럼: {missing} (실제: {list(df.columns)[:10]})")

    for c in ["점포_수", "개업_점포_수", "폐업_점포_수"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["year"] = year
    df["market"] = df["상권_코드"].map(lambda c: MARKETS[c][0])
    df["axis"] = df["상권_코드"].map(lambda c: MARKETS[c][1])
    return df[NEED + ["year", "market", "axis"]]


def main():
    years = [2021, 2022, 2023, 2024, 2025]
    df = pd.concat([read_year(y) for y in years], ignore_index=True)

    n_by_year = df.groupby("year")["상권_코드"].nunique()
    print("=== 연도별 매칭 상권 수 (9개 기대) ===")
    print(n_by_year.to_string(), "\n")

    g = df.groupby(["market", "year"]).agg(
        점포=("점포_수", "sum"), 개업=("개업_점포_수", "sum"), 폐업=("폐업_점포_수", "sum"))
    g["순증"] = g.개업 - g.폐업
    g["폐업률%"] = (g.폐업 / g.점포 * 100).round(1)

    print("=== 시장별 연간 순증(개업-폐업) ===")
    print(g.reset_index().pivot(index="market", columns="year", values="순증").to_string(), "\n")

    print("=== 2025년 폐업률 ===")
    latest = g.xs(2025, level="year")[["점포", "개업", "폐업", "폐업률%"]]
    print(latest.sort_values("폐업률%", ascending=False).to_string(), "\n")

    # 경동시장 업종 구성 — 무엇이 남아 있는가
    kd = df[(df.market == "경동시장") & (df.year == 2025)]
    top = kd.groupby("서비스_업종_코드_명")["점포_수"].sum().nlargest(10)
    print("=== 경동시장 2025년 업종별 점포수 상위 10 ===")
    print(top.to_string())

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    g.reset_index().to_csv(DATA_PROCESSED / "golmok_store_turnover.csv", index=False)
    print(f"\n저장: {DATA_PROCESSED}/golmok_store_turnover.csv")


if __name__ == "__main__":
    main()
