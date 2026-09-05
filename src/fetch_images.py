"""상품 카테고리 실사 이미지 수집 — Wikimedia Commons.

아무 이미지나 커밋할 수 없으므로 Commons API에서 라이선스 메타데이터를 읽어
CC0 · Public domain · CC-BY 계열만 받는다. 출처는 site/img/CREDITS.md 에 기록한다.

    uv run python src/fetch_images.py
"""

import json
import re
import time
from pathlib import Path

import requests

from config import ROOT

OUT = ROOT / "site" / "img"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "chungryangri-market/1.0 (github.com/Gyuhyeon-Eom/chungryangri)"}

OK_LICENSE = re.compile(r"^(CC0|Public domain|CC BY(?!-NC)(-SA)?( \d\.\d)?)", re.I)

# 카테고리 → (파일 슬러그, Commons 검색어) — 영문 검색이 결과가 좋다
QUERIES = {
    "한약재": ("herbs", "dried medicinal herbs traditional"),
    "인삼·홍삼": ("ginseng", "korean ginseng root"),
    "건약초": ("driedherb", "dried goji berries"),
    "밤·견과류": ("chestnut", "sweet chestnuts castanea sativa"),
    "곡류·참기름": ("sesameoil", "sesame oil bottle"),
    "선물세트": ("giftset", "fruit gift basket"),
    "제철 과일": ("apple", "red apples fruit"),
    "청과": ("tomato", "tomatoes market stall"),
    "청과 도매": ("fruitbox", "apple crate"),
    "채소": ("cabbage", "chinese cabbage vegetable market"),
    "농산물": ("potato", "Solanum tuberosum harvest"),
    "수산물": ("mackerel", "mackerel fish"),
    "활어": ("flatfish", "fish market fresh fish ice"),
    "선어": ("cutlass", "largehead hairtail"),
    "패류": ("clam", "clams shellfish"),
    "건어물": ("anchovy", "dried anchovies"),
    "정육": ("pork", "raw pork belly slices"),
    "반찬": ("kimchi", "kimchi bowl"),
    "먹거리": ("mandu", "jiaozi dumplings plate"),
    "통닭": ("chicken", "korean fried chicken whole"),
    "족발": ("jokbal", "jokbal pork trotters"),
    "회": ("hoe", "sashimi platter"),
    "분식": ("tteokbokki", "tteokbokki"),
    "건강식품": ("honey", "honey jar"),
    "미용재료": ("scissors", "hairdressing scissors"),
    "잡화": ("basket", "wicker baskets"),
}


def search(term: str):
    """검색 결과에서 라이선스 통과하는 첫 비트맵을 (썸네일URL, 파일명, 라이선스, 작가)로."""
    r = requests.get(API, params={
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 640,
    }, headers=UA, timeout=30)
    pages = (r.json().get("query") or {}).get("pages", {})
    # 검색 순위 순으로 정렬
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") != "image/jpeg":
            continue
        meta = info.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        if not OK_LICENSE.match(lic):
            continue
        # 그림·판화·오래된 스캔은 상품 사진으로 부적합
        if re.search(r"painting|drawing|scene|engraving|reproduction|voltaic|17\d\d|18\d\d", p["title"], re.I):
            continue
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", "")).strip()
        return info["thumburl"], p["title"], lic, artist[:80]
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    credits = ["# 이미지 출처\n",
               "모든 상품 이미지는 Wikimedia Commons에서 수집했으며 CC0 · Public domain · CC-BY 계열입니다.\n"]
    ok = fail = 0

    for cat, (slug, term) in QUERIES.items():
        dest = OUT / f"{slug}.jpg"
        if dest.exists():
            print(f"  {cat:8} skip")
            ok += 1
            continue
        hit = search(term)
        if not hit:
            print(f"  {cat:8} ❌ 라이선스 통과 결과 없음 ({term})")
            fail += 1
            continue
        url, title, lic, artist = hit
        img = None
        for wait in (0, 10, 25):
            if wait:
                time.sleep(wait)
            img = requests.get(url, headers=UA, timeout=60)
            if img.status_code != 429:
                break
        if img.status_code != 200:
            print(f"  {cat:8} ❌ HTTP {img.status_code}")
            fail += 1
            continue
        dest.write_bytes(img.content)
        credits.append(f"- **{cat}** `{slug}.jpg` — [{title}](https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}) · {lic}" + (f" · {artist}" if artist else ""))
        print(f"  {cat:8} ✅ {lic:14} {len(img.content)//1024}KB  {title[:50]}")
        ok += 1
        time.sleep(1.5)

    (OUT / "CREDITS.md").write_text("\n".join(credits), encoding="utf-8")
    mapping = {cat: f"img/{slug}.jpg" for cat, (slug, _) in QUERIES.items()}
    (OUT / "map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n완료 {ok} / 실패 {fail} · 출처 기록: site/img/CREDITS.md")


if __name__ == "__main__":
    main()
