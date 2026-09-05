"""서울시 상권분석서비스(골목상권) 파일 수집.

서울 열린데이터광장 파일 다운로드는 인증키 없이 POST 한 번으로 끝난다.
다만 파일 목록이 JS로 그려져서 seq 값을 페이지에서 긁을 수 없다.
아래 seq는 브라우저로 확인해 적어둔 값이다(2026-08 기준). 목록이 바뀌면
datasetView 페이지에서 span[onclick*="downloadFile"] 의 인자를 다시 확인할 것.

⚠️ 2024년부터 상권 공간단위가 '표준단위구역'으로 바뀌어 상권코드가 단절된다.
   2021~2023 과 2024~2025 를 하나의 시계열로 이으면 안 된다.

    uv run python src/download_golmok.py
"""

import re
import time
import zipfile

import requests

from config import DATA_RAW

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
OUT = DATA_RAW / "golmok"

# (infId, seq, 저장이름)
FILES = [
    ("OA-15572", "51", "추정매출_2025.zip"),
    ("OA-15572", "50", "추정매출_2024.zip"),
    ("OA-15572", "49", "추정매출_2023.zip"),
    ("OA-15572", "48", "추정매출_2022.zip"),
    ("OA-15572", "47", "추정매출_2021.zip"),
    ("OA-15577", "20", "점포_2025.zip"),
    ("OA-15577", "19", "점포_2024.zip"),
    ("OA-15577", "18", "점포_2023.zip"),
    ("OA-15577", "17", "점포_2022.zip"),
    ("OA-15577", "16", "점포_2021.zip"),
    ("OA-15560", "5", "영역_상권.zip"),
]


_INF_SEQ_CACHE: dict[str, str] = {}


def inf_seq(session, inf_id: str, probe_seq: str) -> str:
    """데이터셋마다 infSeq가 다르다(생활인구 1, 상권분석 3).

    페이지 HTML의 hidden input 값은 JS가 나중에 덮어써서 믿을 수 없다.
    그래서 1~4를 실제로 눌러보고 파일이 돌아오는 값을 찾는다.
    틀린 값이면 서버가 '잘못된 접근입니다' 알림 HTML을 200으로 돌려준다.
    """
    if inf_id in _INF_SEQ_CACHE:
        return _INF_SEQ_CACHE[inf_id]

    referer = f"https://data.seoul.go.kr/dataList/{inf_id}/F/1/datasetView.do"
    session.get(referer, timeout=(30, 120))
    for candidate in ("1", "2", "3", "4"):
        r = session.post(URL, data={"infId": inf_id, "seqNo": "", "seq": probe_seq,
                                    "infSeq": candidate},
                         headers={"Referer": referer}, stream=True, timeout=(30, 120))
        is_file = "html" not in r.headers.get("content-type", "").lower()
        r.close()
        if is_file:
            _INF_SEQ_CACHE[inf_id] = candidate
            return candidate
    raise RuntimeError(f"{inf_id}: 유효한 infSeq를 찾지 못했습니다")


def fetch(session, inf_id, seq, dest) -> int:
    referer = f"https://data.seoul.go.kr/dataList/{inf_id}/F/1/datasetView.do"
    with session.post(URL,
                      data={"infId": inf_id, "seqNo": "", "seq": seq,
                            "infSeq": inf_seq(session, inf_id, seq)},
                      headers={"Referer": referer}, stream=True, timeout=(30, 600)) as r:
        r.raise_for_status()
        if "html" in r.headers.get("content-type", "").lower():
            raise RuntimeError("HTML 응답 — 파일이 아닙니다")
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
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    started = time.time()

    for i, (inf_id, seq, name) in enumerate(FILES, 1):
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i:>2}/{len(FILES)}] {name}  skip ({dest.stat().st_size/1e6:,.1f}MB)")
            continue
        try:
            size = fetch(session, inf_id, seq, dest)
            with zipfile.ZipFile(dest) as z:
                inner = len([n for n in z.namelist() if n.lower().endswith(".csv")])
            print(f"[{i:>2}/{len(FILES)}] {name}  {size/1e6:,.1f}MB · CSV {inner}개", flush=True)
        except Exception as exc:
            print(f"[{i:>2}/{len(FILES)}] {name}  실패 {type(exc).__name__}: {exc}", flush=True)

    total = sum(f.stat().st_size for f in OUT.glob("*.zip")) / 1e6
    print(f"\n완료 {len(list(OUT.glob('*.zip')))}개 · {total:,.0f}MB · {(time.time()-started)/60:.1f}분")


if __name__ == "__main__":
    main()
