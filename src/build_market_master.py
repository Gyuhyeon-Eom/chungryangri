"""시장 마스터 테이블에 소상공인시장진흥공단 공식 통계를 결합한다.

data/geo/markets_master.csv 는 문헌·언론 조사로 만든 뼈대이고,
여기에 시장_점포수_종사자.csv(소진공)의 점포수·빈점포·상인수를 붙여
data/processed/markets_enriched.csv 를 만든다.

시장명 표기가 소스마다 달라(띄어쓰기 등) 정규화 후 매칭한다.
"""

import re

import pandas as pd

from config import DATA_GEO, DATA_PROCESSED, DATA_RAW, TABLES

SBIZ_STORES = DATA_RAW / "data_go_kr" / "시장_점포수_종사자.csv"


def read_korean_csv(path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(f"인코딩 판별 실패: {path}")


def normalize(name: str) -> str:
    """'청량리 청과물시장' 과 '청량리청과물시장' 을 같은 키로 만든다."""
    return re.sub(r"\s+", "", str(name)).strip()


def main():
    master = pd.read_csv(DATA_GEO / "markets_master.csv")
    sbiz = read_korean_csv(SBIZ_STORES)
    ddm = sbiz[sbiz["시군구"].astype(str).str.contains("동대문", na=False)].copy()

    master["_key"] = master["market_name"].map(normalize)
    ddm["_key"] = ddm["시장명"].map(normalize)

    keep = {
        "시장면적": "area_sqm_sbiz",
        "전체점포": "stores_total",
        "빈점포": "stores_vacant",
        "노점수": "street_stalls",
        "점포상인": "merchants_store",
        "총시장상인": "merchants_total",
    }
    merged = master.merge(ddm[["_key", *keep]].rename(columns=keep), on="_key", how="left")

    unmatched = merged[merged["stores_total"].isna()]["market_name"].tolist()
    if unmatched:
        print(f"⚠ 미매칭 {len(unmatched)}개: {', '.join(unmatched)}")

    # 공실률 = 빈점포 / 전체점포. 노점은 점포가 아니므로 분모에서 제외.
    merged["vacancy_rate"] = (merged.stores_vacant / merged.stores_total * 100).round(1)
    # 문헌 면적과 공단 면적이 얼마나 다른지 기록해둔다 (출처 불일치 추적용)
    merged["area_gap_pct"] = (
        (merged.area_sqm_sbiz - merged.area_sqm) / merged.area_sqm * 100
    ).round(1)

    merged = merged.drop(columns="_key").sort_values("stores_total", ascending=False)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out = DATA_PROCESSED / "markets_enriched.csv"
    merged.to_csv(out, index=False)
    print(f"저장: {out}  ({len(merged)}개 시장)")

    view = merged[
        ["market_name", "axis_label", "stores_total", "stores_vacant",
         "vacancy_rate", "street_stalls", "merchants_total"]
    ]
    print("\n=== 시장별 현황 (점포수 순) ===")
    print(view.to_string(index=False))

    print("\n=== 기능축별 집계 ===")
    axis = merged.groupby(["axis", "axis_label"], as_index=False).agg(
        시장수=("market_id", "count"),
        전체점포=("stores_total", "sum"),
        빈점포=("stores_vacant", "sum"),
        노점=("street_stalls", "sum"),
        상인=("merchants_total", "sum"),
    )
    axis["공실률%"] = (axis.빈점포 / axis.전체점포 * 100).round(1)
    print(axis.to_string(index=False))

    total, vacant = merged.stores_total.sum(), merged.stores_vacant.sum()
    print(f"\n클러스터 합계: 점포 {total:,.0f}개 · 빈점포 {vacant:,.0f}개 "
          f"· 공실률 {vacant / total * 100:.1f}% · 상인 {merged.merchants_total.sum():,.0f}명")

    TABLES.mkdir(parents=True, exist_ok=True)
    view.to_csv(TABLES / "market_status.csv", index=False)


if __name__ == "__main__":
    main()
