"""공간 분석 — 앞선 분석의 한계를 실측으로 해소한다.

보고서에 '한계'로 적어둔 항목 중 세 가지는 이미 확보한 자료로 검증이 가능하다.

  한계 1. 상권 영역이 시장 물리적 경계보다 넓다
          → 상권 폴리곤에 점포 좌표를 공간 조인해 실제 구성을 확인
  한계 2. 스타벅스 경동1960이 경동시장 상권에 포함되는지 미확인
          → 상권 폴리곤 안에 해당 점포가 있는지 직접 조회
  한계 3. 배후인구를 행정동으로 잡아 해상도가 낮다
          → 시장 중심에서 반경 500m 내 집계구만 골라 다시 집계

    uv run python src/analyze_spatial.py
"""

import re

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from analyze_golmok import MARKETS
from config import DATA_INTERIM, DATA_PROCESSED, DATA_RAW

SHP = DATA_RAW / "golmok" / "shp" / "trade_area.shp"
STORES = DATA_INTERIM / "sangga_ddm" / "sangga_20260630_ddm.csv"
CRS_M = "EPSG:5181"   # 상권 폴리곤 좌표계 (미터 단위)


def load_areas() -> gpd.GeoDataFrame:
    g = gpd.read_file(SHP)
    g = g[g.TRDAR_CD.isin(MARKETS)].copy()
    g["market"] = g.TRDAR_CD.map(lambda c: MARKETS[c][0])
    g["상권면적_㎡"] = g.RELM_AR
    return g.set_crs(CRS_M, allow_override=True)


def load_stores() -> gpd.GeoDataFrame:
    df = pd.read_csv(STORES, low_memory=False)
    df = df.dropna(subset=["경도", "위도"])
    pts = gpd.GeoDataFrame(
        df, geometry=[Point(x, y) for x, y in zip(df.경도, df.위도)], crs="EPSG:4326")
    return pts.to_crs(CRS_M)


def main():
    areas = load_areas()
    stores = load_stores()
    print(f"상권 폴리곤 {len(areas)}개 · 동대문구 점포 {len(stores):,}개\n")

    # ---- 1) 상권 안의 실제 점포 ----
    joined = gpd.sjoin(stores, areas[["market", "geometry"]], predicate="within")
    cnt = joined.groupby("market").size().rename("상권내_점포")

    # 소진공 시장 등록 점포수 (2023년 연도별 자료 기준)
    reg = pd.read_csv(DATA_PROCESSED / "vacancy_timeseries.csv")
    reg = reg[reg.year == 2023].set_index("market")["total"].rename("시장_등록점포")

    cmp = pd.concat([cnt, reg], axis=1).dropna()
    cmp["배율"] = cmp.상권내_점포 / cmp.시장_등록점포
    cmp = cmp.join(areas.set_index("market")["상권면적_㎡"])
    print("=== ① 상권 영역과 시장 등록 점포의 괴리 ===")
    print(cmp.sort_values("배율", ascending=False).round(1).to_string(), "\n")

    # ---- 2) 스타벅스 경동1960 귀속 ----
    print("=== ② 경동시장 상권 내 커피전문점 ===")
    kd = joined[joined.market == "경동시장"]
    cafe = kd[kd.상권업종소분류명.astype(str).str.contains("커피|카페", na=False)]
    print(f"경동시장 상권 내 커피·카페 {len(cafe)}개")
    sb = joined[joined.상호명.astype(str).str.contains("스타벅스", na=False)]
    if len(sb):
        print(sb[["상호명", "market", "상권업종소분류명"]].to_string(index=False))
    else:
        print("동대문구 상가정보에 '스타벅스' 상호 없음")
        near = stores[stores.상호명.astype(str).str.contains("스타벅스", na=False)]
        print(f"(동대문구 전체 스타벅스 {len(near)}개 — 상권 폴리곤 밖)")
    print()

    # ---- 3) 상권별 업종 구성 (경계 문제의 실체) ----
    print("=== ③ 서울약령시장 상권 내 실제 업종 상위 8 ===")
    yak = joined[joined.market == "서울약령시장"]
    top = yak.상권업종중분류명.value_counts().head(8)
    print((top / len(yak) * 100).round(1).to_string(), "\n")

    # ---- 4) 시장 반경 500m 배후인구 ----
    print("=== ④ 시장 반경 500m 내 집계구 (배후인구 재정의) ===")
    cen = areas.copy()
    cen["geometry"] = cen.geometry.centroid
    buf = cen.copy()
    buf["geometry"] = buf.geometry.buffer(500)
    print(f"시장 9개 중심에서 반경 500m 버퍼 생성 · 합집합 면적 "
          f"{buf.union_all().area / 1e6:.2f}㎢")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    cmp.to_csv(DATA_PROCESSED / "area_vs_market.csv")
    (top / len(yak) * 100).round(2).to_csv(DATA_PROCESSED / "yak_industry_mix.csv")
    print(f"\n저장: {DATA_PROCESSED}/area_vs_market.csv 외 1건")


if __name__ == "__main__":
    main()
