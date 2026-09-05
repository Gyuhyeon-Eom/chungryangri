"""소진공 연도별 공실 데이터의 신뢰성을 검증한다.

청량리전통시장의 '2022년 회복'과 경동시장의 '46.6% 고착'을 조사하다가
두 현상 모두 실제 상권 변화가 아니라 통계 산출의 산물일 가능성이 드러났다.
이 스크립트는 그 근거를 전국 데이터로 정량화한다.

검증 항목
  1) 전년과 (영업, 빈점포)가 완전히 동일한 시장의 비율 — 매년 새로 조사되는가
  2) 총점포수(분모)가 전년 대비 크게 변동한 시장의 비율 — 모집단이 안정적인가
  3) 전국 공실률 추세 — 2022년에 전국적 회복이 있었는가

    uv run python src/verify_vacancy_data.py
"""

import re

import pandas as pd

from config import DATA_PROCESSED, DATA_RAW

SRC = DATA_RAW / "data_go_kr" / "vacancy"


def read_all() -> pd.DataFrame:
    rows = []
    for path in sorted(SRC.rglob("*.csv")):
        year = int(re.search(r"\((\d{4})년\)", path.name).group(1))
        for enc in ("cp949", "utf-8-sig"):
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        df.columns = [c.strip() for c in df.columns]
        o = next(c for c in df.columns if "영업점포" in c)
        v = next(c for c in df.columns if "빈점포" in c)
        a = next((c for c in df.columns if "주소" in c), None)
        out = pd.DataFrame({
            "market": df["시장명"].astype(str).str.replace(r"\s+", "", regex=True),
            "addr": df[a].astype(str) if a else "",
            "open": pd.to_numeric(df[o], errors="coerce"),
            "vacant": pd.to_numeric(df[v], errors="coerce"),
        })
        out["year"] = year
        rows.append(out)
    df = pd.concat(rows, ignore_index=True).dropna(subset=["open", "vacant"])
    df["total"] = df["open"] + df["vacant"]
    df["key"] = df.market + "|" + df.addr.str.replace(r"\s+", "", regex=True).str[:14]
    return df


def main():
    df = read_all()
    years = sorted(df.year.unique())
    print(f"전국 {df.key.nunique():,}개 시장 · {years[0]}~{years[-1]} ({len(years)}개 연도)\n")

    # ---- 1) 전년과 완전히 동일한 기록의 비율 ----
    print("=== ① 전년도와 (영업,빈점포)가 완전히 동일한 시장 비율 ===")
    print("   매년 새로 조사한다면 이 비율은 낮아야 한다.")
    rows = []
    for prev, cur in zip(years, years[1:]):
        a = df[df.year == prev].set_index("key")[["open", "vacant"]]
        b = df[df.year == cur].set_index("key")[["open", "vacant"]]
        both = a.join(b, how="inner", lsuffix="_p", rsuffix="_c")
        same = ((both.open_p == both.open_c) & (both.vacant_p == both.vacant_c)).mean() * 100
        rows.append({"구간": f"{prev}→{cur}", "동일비율%": round(same, 1), "대상시장": len(both)})
    dup = pd.DataFrame(rows)
    print(dup.to_string(index=False), "\n")

    # ---- 2) 분모(총점포수) 안정성 ----
    print("=== ② 총점포수가 전년 대비 ±20% 이상 변동한 시장 비율 ===")
    print("   모집단이 안정적이라면 이 비율도 낮아야 한다.")
    rows = []
    for prev, cur in zip(years, years[1:]):
        a = df[df.year == prev].set_index("key")["total"]
        b = df[df.year == cur].set_index("key")["total"]
        j = pd.concat([a.rename("p"), b.rename("c")], axis=1, join="inner")
        j = j[j.p > 0]
        big = ((j.c / j.p - 1).abs() > 0.2).mean() * 100
        rows.append({"구간": f"{prev}→{cur}", "±20%초과%": round(big, 1)})
    print(pd.DataFrame(rows).to_string(index=False), "\n")

    # ---- 3) 전국 공실률 추세 ----
    print("=== ③ 전국 총 공실률 추세 ===")
    nat = df.groupby("year").agg(open=("open", "sum"), vacant=("vacant", "sum"))
    nat["공실률%"] = (nat.vacant / (nat.open + nat.vacant) * 100).round(2)
    print(nat[["공실률%"]].to_string(), "\n")

    # ---- 4) 청량리 클러스터 개별 확인 ----
    print("=== ④ 청량리 주요 시장의 영업점포수 추이 (분모 영향 없는 지표) ===")
    targets = ["청량리전통시장", "경동시장", "서울약령시장", "청량리종합시장"]
    sub = df[df.market.isin(targets) & df.addr.str.contains("동대문", na=False)]
    piv = sub.pivot_table(index="market", columns="year", values="open")
    print(piv.to_string(na_rep="—"), "\n")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    dup.to_csv(DATA_PROCESSED / "vacancy_data_quality.csv", index=False)
    nat.to_csv(DATA_PROCESSED / "vacancy_national_trend.csv")
    piv.to_csv(DATA_PROCESSED / "cluster_open_stores.csv")
    print(f"저장: {DATA_PROCESSED}/vacancy_data_quality.csv 외 2건")


if __name__ == "__main__":
    main()
