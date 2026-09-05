"""상품 단위 이미지 수집 — 카테고리 이미지와 상품이 어긋나는 것들만.

예: '딸기'가 청과 카테고리라 토마토 사진이 붙는 문제.
여기서 받은 이미지는 site/img/p/ 에 들어가고, 프런트는
상품명 → 카테고리 → No Image 순으로 해상한다.

    uv run python src/fetch_product_images.py
"""

import json
import time

from config import ROOT
from fetch_images import OUT as IMG_DIR, search

P_DIR = ROOT / "site" / "img" / "p"

# 상품명 → (슬러그, Commons 검색어). 카테고리 사진과 실제로 어긋나는 것만.
PRODUCTS = {
    "딸기": ("strawberry", "strawberries fruit"),
    "배": ("pear", "asian pear nashi fruit"),
    "감귤": ("mandarin", "mandarin oranges citrus"),
    "호두": ("walnut", "walnuts shelled"),
    "대추": ("jujube", "dried jujube fruit"),
    "들기름": ("perillaoil", "perilla oil bottle"),
    "찹쌀": ("rice", "glutinous rice grains"),
    "오징어": ("squid", "fresh squid market"),
    "갈치": ("hairtail", "largehead hairtail fish"),
    "조기": ("croaker", "yellow croaker fish"),
    "광어": ("flounder", "olive flounder fish market"),
    "우럭": ("rockfish", "korean rockfish"),
    "홍합": ("mussel", "mussels shellfish fresh"),
    "다시마": ("kelp", "dried kelp kombu"),
    "고구마": ("sweetpotato", "sweet potatoes"),
    "한우 등심": ("beef", "beef sirloin raw"),
    "장아찌": ("jangajji", "korean pickles jangajji"),
    "찹쌀도넛": ("donut", "korean twisted doughnut"),
    "사과(박스)": ("applebox", "apples in crate"),
    "배(박스)": ("pearbox", "asian pears box"),
    "삼겹살": ("porkbelly", "raw pork belly sliced"),
    "김치": ("kimchi2", "kimchi cabbage fermented"),
    "멸치": ("anchovy2", "dried anchovies korean"),
    "고등어": ("mackerel2", "chub mackerel fresh"),
    "옛날 통닭": ("tongdak", "whole fried chicken korean"),
    "바지락": ("manilaclam", "manila clams"),
    "양파": ("onion", "onions bulbs"),
    "대파": ("scallion", "welsh onion scallions bundle"),
    "토마토": ("tomato2", "ripe tomatoes"),
    "사과": ("apple2", "red apples"),
}


def main():
    P_DIR.mkdir(parents=True, exist_ok=True)
    mapping, credits = {}, []
    ok = fail = 0

    for name, (slug, term) in PRODUCTS.items():
        dest = P_DIR / f"{slug}.jpg"
        if dest.exists():
            mapping[name] = f"img/p/{slug}.jpg"
            ok += 1
            continue
        hit = None
        for wait in (0, 12, 30):
            if wait:
                time.sleep(wait)
            try:
                hit = search(term)
                break
            except Exception:
                continue
        if not hit:
            print(f"  {name:8} ❌ 검색 실패")
            fail += 1
            continue
        url, title, lic, artist = hit
        import requests
        from fetch_images import UA
        img = None
        for wait in (0, 10, 25):
            if wait:
                time.sleep(wait)
            img = requests.get(url, headers=UA, timeout=60)
            if img.status_code != 429:
                break
        if img.status_code != 200:
            print(f"  {name:8} ❌ HTTP {img.status_code}")
            fail += 1
            continue
        dest.write_bytes(img.content)
        mapping[name] = f"img/p/{slug}.jpg"
        credits.append(f"- **{name}** `p/{slug}.jpg` — [{title}](https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}) · {lic}" + (f" · {artist}" if artist else ""))
        print(f"  {name:8} ✅ {lic:14} {title[:46]}")
        ok += 1
        time.sleep(2.5)

    (P_DIR / "map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    if credits:
        prev = (IMG_DIR / "CREDITS.md").read_text(encoding="utf-8")
        (IMG_DIR / "CREDITS.md").write_text(prev + "\n\n## 상품 단위 이미지\n" + "\n".join(credits), encoding="utf-8")
    print(f"\n완료 {ok} / 실패 {fail}")


if __name__ == "__main__":
    main()
