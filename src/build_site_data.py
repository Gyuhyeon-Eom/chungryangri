"""커머스 사이트용 데이터 생성.

사이트의 구조가 분석 결과에서 나오도록, 하드코딩 대신 처리된 CSV에서 뽑는다.
  - 시장 유형(군집)        → B2B/B2C 노출 기준
  - 시간대·요일 매출 구성  → 영업 성격 표시
  - 업종 구성비            → 카테고리 구성
  - 연령대 구성            → 타깃 표기

    uv run python src/build_site_data.py
"""

import json

import pandas as pd

from config import DATA_PROCESSED, ROOT

OUT = ROOT / "site" / "data.json"

BANDS = ["00~06", "06~11", "11~14", "14~17", "17~21", "21~24"]
DOW = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
CLUSTER = {1: "주말 소매형", 2: "평일 도매형", 3: "혼합 대형", 4: "근린 생필품형"}

# 유형 → 판매 채널. 도매형은 B2B, 소매형은 B2C, 대형은 양쪽.
CHANNEL = {"평일 도매형": ["b2b"], "혼합 대형": ["b2b", "b2c"],
           "주말 소매형": ["b2c"], "근린 생필품형": ["b2c"]}

# 시장별 대표 품목 — 상가업소 업종 구성과 문헌 조사를 반영
GOODS = {
    "서울약령시장": ["한약재", "인삼·홍삼", "건약초", "청과 도매"],
    "경동시장": ["청과", "건어물", "미용재료", "정육"],
    "경동광성상가": ["한약재", "건강식품", "잡화"],
    "청량리종합시장": ["밤·견과류", "곡류·참기름", "선물세트", "반찬"],
    "청량리청과물시장": ["제철 과일", "채소", "청과 도매"],
    "동서시장": ["청과", "채소", "먹거리"],
    "청량리농수산물시장": ["농산물", "수산물", "건어물"],
    "청량리수산시장": ["활어", "선어", "패류"],
    "청량리전통시장": ["통닭", "족발", "회", "분식"],
}


# 카테고리별 대표 상품. (도매단위, 도매가) / (소매단위, 소매가)
def _p(name, b2b, b2c, origin="국내산"):
    return {"name": name, "b2b": b2b, "b2c": b2c, "origin": origin}


CATALOG = {
    "한약재": [_p("황기", ("1kg", 18000), ("300g", 7500)),
             _p("당귀", ("1kg", 24000), ("300g", 9800)),
             _p("감초", ("1kg", 15000), ("300g", 6500))],
    "인삼·홍삼": [_p("6년근 수삼", ("1채(750g)", 62000), ("1채(750g)", 78000)),
                _p("홍삼 절편", ("500g", 45000), ("100g", 12000))],
    "건약초": [_p("작약", ("1kg", 21000), ("300g", 8500)),
             _p("구기자", ("1kg", 26000), ("300g", 10500))],
    "밤·견과류": [_p("햇밤", ("10kg", 78000), ("1kg", 9800)),
               _p("호두", ("5kg", 92000), ("500g", 11500)),
               _p("대추", ("5kg", 68000), ("500g", 8900))],
    "곡류·참기름": [_p("참기름", ("1.8L", 42000), ("320ml", 12000)),
                 _p("들기름", ("1.8L", 48000), ("320ml", 13500)),
                 _p("찹쌀", ("20kg", 76000), ("2kg", 9500))],
    "선물세트": [_p("견과 선물세트", ("10세트", 280000), ("1세트", 35000)),
               _p("참기름 선물세트", ("10세트", 320000), ("1세트", 39000))],
    "제철 과일": [_p("사과", ("10kg", 42000), ("1.5kg", 9800)),
               _p("배", ("10kg", 48000), ("1.5kg", 11500)),
               _p("감귤", ("10kg", 32000), ("1.5kg", 7900))],
    "청과": [_p("토마토", ("10kg", 36000), ("1kg", 5900)),
           _p("딸기", ("2kg", 28000), ("500g", 9500))],
    "청과 도매": [_p("사과(박스)", ("15kg", 58000), ("15kg", 66000)),
               _p("배(박스)", ("15kg", 64000), ("15kg", 72000))],
    "채소": [_p("대파", ("10kg", 22000), ("1단", 3500)),
           _p("양파", ("15kg", 24000), ("2kg", 4900))],
    "농산물": [_p("고구마", ("10kg", 34000), ("2kg", 8500)),
            _p("감자", ("10kg", 26000), ("2kg", 6500))],
    "수산물": [_p("고등어", ("10kg", 68000), ("2마리", 8900)),
            _p("오징어", ("5kg", 72000), ("2마리", 9500))],
    "활어": [_p("광어", ("1kg", 32000), ("1kg", 42000)),
           _p("우럭", ("1kg", 28000), ("1kg", 36000))],
    "선어": [_p("갈치", ("5kg", 88000), ("1마리", 12000)),
           _p("조기", ("5kg", 64000), ("3마리", 9800))],
    "패류": [_p("바지락", ("10kg", 42000), ("1kg", 6500)),
           _p("홍합", ("10kg", 28000), ("1kg", 4500))],
    "건어물": [_p("멸치", ("3kg", 78000), ("500g", 15900)),
            _p("다시마", ("3kg", 42000), ("300g", 6900))],
    "정육": [_p("삼겹살", ("10kg", 158000), ("500g", 12900)),
           _p("한우 등심", ("5kg", 420000), ("300g", 32000))],
    "반찬": [_p("김치", ("10kg", 48000), ("1kg", 8900)),
           _p("장아찌", ("5kg", 38000), ("500g", 6500))],
    "먹거리": [_p("찹쌀도넛", ("50개", 35000), ("5개", 5000)),
            _p("수제 만두", ("100개", 48000), ("10개", 7000))],
    "통닭": [_p("옛날 통닭", ("10마리", 130000), ("1마리", 16000))],
    "족발": [_p("족발", ("5인분", 78000), ("1인분", 19000))],
    "회": [_p("모둠회", ("5인분", 145000), ("1인분", 35000))],
    "분식": [_p("떡볶이", ("10인분", 45000), ("1인분", 5500))],
    "건강식품": [_p("도라지청", ("10병", 120000), ("1병", 15000)),
              _p("배도라지즙", ("100포", 85000), ("30포", 32000))],
    "미용재료": [_p("미용 가위", ("10개", 180000), ("1개", 24000)),
              _p("펌 롯드", ("50세트", 95000), ("1세트", 2500))],
    "잡화": [_p("주방 소도구", ("50개", 65000), ("1개", 2000))],
}


def peak_label(row) -> str:
    """시간대 구성비에서 가장 큰 두 구간을 영업 성격으로 표기."""
    top = row[BANDS].astype(float).nlargest(2).index.tolist()
    return " · ".join(sorted(top))


def main():
    tp = pd.read_csv(DATA_PROCESSED / "golmok_time_profile.csv")
    dw = pd.read_csv(DATA_PROCESSED / "sales_dow.csv", index_col=0)
    clus = pd.read_csv(DATA_PROCESSED / "market_clusters.csv", index_col=0)
    age = pd.read_csv(DATA_PROCESSED / "golmok_age_by_year.csv")
    bm = pd.read_csv(DATA_PROCESSED / "seoul_benchmark.csv")
    dt = pd.read_csv(DATA_PROCESSED / "ticket_decomp.csv", index_col=0)

    a25 = age[age.year == 2025].set_index("market")
    growth = bm[bm["청량리"]].set_index("name")

    markets = []
    for m, r in clus.iterrows():
        kind = CLUSTER[int(r["군집_4"])]
        t = tp[tp.market == m].iloc[0]
        wknd = float(dw.loc[m, "주말비중"])
        senior = float(a25.loc[m, "60대+"]) if m in a25.index else None
        youth = float(a25.loc[m, "20대"] + a25.loc[m, "30대"]) if m in a25.index else None

        # 상권분석 상권명과 표기가 다른 경우 보정
        gk = next((k for k in growth.index if k.replace(" ", "").startswith(m[:4])), None)

        markets.append({
            "name": m,
            "kind": kind,
            "channels": CHANNEL[kind],
            "goods": GOODS.get(m, []),
            "peak": peak_label(t),
            "weekendShare": round(wknd, 1),
            "seniorShare": round(senior, 1) if senior else None,
            "youthShare": round(youth, 1) if youth else None,
            "ticket": int(dt.loc[m, "객단가25"]) if m in dt.index else None,
            "growth": round(float(growth.loc[gk, "growth"]), 1) if gk else None,
            "timeProfile": {b: round(float(t[b]), 1) for b in BANDS},
            "dowProfile": {d: round(float(dw.loc[m, d]), 1) for d in DOW},
        })

    # 카테고리 — 대표 품목을 펼쳐 중복 제거
    cats = []
    for m in markets:
        for g in m["goods"]:
            if g not in cats:
                cats.append(g)

    # 상품 — 시장의 채널에 맞춰 도매/소매 단위를 다르게 붙인다
    products = []
    for m in markets:
        for g in m["goods"]:
            spec = CATALOG.get(g)
            if not spec:
                continue
            for item in spec:
                for ch in m["channels"]:
                    unit, price = (item["b2b"] if ch == "b2b" else item["b2c"])
                    products.append({
                        "id": f"{m['name'][:2]}-{item['name']}-{ch}",
                        "name": item["name"],
                        "category": g,
                        "market": m["name"],
                        "channel": ch,
                        "unit": unit,
                        "price": price,
                        "origin": item.get("origin", "국내산"),
                    })

    payload = {
        "updated": "2026-08",
        "summary": {
            "markets": len(markets),
            "stores": 2588,
            "merchants": 6766,
            "seoulRank": "서울 전통시장 283개 중 8개 시장이 상위 20% 이내",
        },
        "categories": cats,
        "markets": markets,
        "products": products,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {OUT}")
    print(f"  시장 {len(markets)}개 · 카테고리 {len(cats)}개 · 상품 {len(products)}개")
    for m in markets:
        print(f"    {m['name']:12} {m['kind']:9} {'/'.join(m['channels']):8} "
              f"주말 {m['weekendShare']:>4}% · 60대+ {m['seniorShare']}%")


if __name__ == "__main__":
    main()
