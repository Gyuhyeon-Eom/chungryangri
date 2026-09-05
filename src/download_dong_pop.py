"""행정동 단위 서울 생활인구(OA-14991) 수집 — 서울 전역.

탄력성 추정의 표본을 늘리기 위한 자료다.
청량리 9개 시장 × 20분기 = 180개 관측치로는 신뢰구간이 너무 넓었다.
서울 전통시장 283개로 넓히면 5천 개대가 되는데, 그러려면 서울 전역의
배후인구가 필요하다. 집계구 단위(월 1GB)는 과하므로 행정동 단위를 쓴다.

파일 구성이 시기별로 다르다. 2023년 이후는 월별, 2021~2022년은 반기 묶음이다.

    uv run python src/download_dong_pop.py
"""

import time
import zipfile

import requests

from config import DATA_RAW
from download_golmok import URL, UA, inf_seq

INF_ID = "OA-14991"
OUT = DATA_RAW / "dong_pop"

# (seq, 저장이름) — 매출 자료와 같은 2021~2025년 구간
FILES = [(f"{y % 100:02d}{m:02d}", f"{y}{m:02d}.zip")
         for y in range(2023, 2026) for m in range(1, 13)]
FILES += [("2224", "2022_하반기.zip"), ("2223", "2022_상반기.zip"),
          ("2222", "2021_하반기.zip"), ("2221", "2021_상반기.zip")]


def fetch(session, seq, dest) -> int:
    referer = f"https://data.seoul.go.kr/dataList/{INF_ID}/F/1/datasetView.do"
    with session.post(URL,
                      data={"infId": INF_ID, "seqNo": "", "seq": seq,
                            "infSeq": inf_seq(session, INF_ID, seq)},
                      headers={"Referer": referer}, stream=True, timeout=(30, 900)) as r:
        r.raise_for_status()
        if "html" in r.headers.get("content-type", "").lower():
            raise RuntimeError("HTML 응답")
        expected = int(r.headers.get("content-length") or 0)
        tmp = dest.with_suffix(".part")
        size = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                size += len(chunk)
        if expected and size != expected:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"불완전 {size:,}/{expected:,}")
        tmp.rename(dest)
        return size


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    started = time.time()
    ok = fail = 0

    for i, (seq, name) in enumerate(FILES, 1):
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i:>2}/{len(FILES)}] {name}  skip")
            ok += 1
            continue
        try:
            size = fetch(s, seq, dest)
            with zipfile.ZipFile(dest) as z:
                n = len([x for x in z.namelist() if x.lower().endswith(".csv")])
            print(f"[{i:>2}/{len(FILES)}] {name}  {size/1e6:,.0f}MB · CSV {n}개  "
                  f"[{(time.time()-started)/60:.0f}분]", flush=True)
            ok += 1
        except Exception as exc:
            print(f"[{i:>2}/{len(FILES)}] {name}  실패 {type(exc).__name__}: {exc}", flush=True)
            fail += 1

    total = sum(f.stat().st_size for f in OUT.glob("*.zip")) / 1e9
    print(f"\n완료 {ok}/{len(FILES)} · {total:.1f}GB · {(time.time()-started)/60:.0f}분")
    if fail:
        print("→ 같은 명령을 다시 실행하면 실패분만 재시도합니다.")


if __name__ == "__main__":
    main()
