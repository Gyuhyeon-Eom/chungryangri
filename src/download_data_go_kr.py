"""공공데이터포털(data.go.kr) 파일데이터 자동 다운로드.

포털이 다운로드 URL을 2단계로 감춰놔서 브라우저로만 받을 수 있는 것처럼 보이지만,
아래 순서로 인증키·로그인 없이 받을 수 있다:

  1) 데이터셋 페이지에서 publicDataDetailPk(uddi:...)를 긁는다
  2) /tcs/dss/selectFileDataDownload.do 에 publicDataTyCode=PR0051 을 붙여 호출 →
     실제 파일 식별자 atchFileId 를 받는다   ← 이 파라미터가 없으면 null이 돌아온다
  3) /cmm/cmm/fileDownload.do?atchFileId=..&fileDetailSn=.. 로 내려받는다

사용:
    uv run python src/download_data_go_kr.py            # 등록된 데이터셋 전부
    uv run python src/download_data_go_kr.py 15012894   # 특정 데이터셋만
"""

import re
import sys
import time
from urllib.parse import unquote

import requests

from config import DATA_RAW

BASE = "https://www.data.go.kr"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
OUT_DIR = DATA_RAW / "data_go_kr"

# 청량리 분석에 필요한 데이터셋. page_type 은 URL 경로가 달라서 구분한다.
DATASETS = [
    ("15012894", "standard", "전국전통시장표준데이터 — 시장 좌표·유형·점포수·개설연도"),
    ("15143951", "fileData", "연도별 전통시장 영업점포수·빈점포수 (2006~2023 공실률 시계열)"),
    ("15052837", "fileData", "소상공인시장진흥공단 전통시장현황 — 면적·빈점포·상인수"),
    ("15117652", "fileData", "소상공인시장진흥공단 시장별 점포수"),
    ("15067631", "fileData", "상가(상권)정보 업종코드 — 상가정보 조인용"),
    ("3060395", "fileData", "전국 전통시장 지원 현황 — 정책 효과 검증용"),
]


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def find_detail_pks(session: requests.Session, ds_id: str, page_type: str) -> list[str]:
    """데이터셋 페이지에서 파일 식별자(uddi)를 최신순으로 긁는다."""
    url = f"{BASE}/data/{ds_id}/{page_type}.do"
    # 표준데이터 페이지는 HTML이 1MB를 넘어 응답이 느리다
    html = session.get(url, timeout=(30, 300)).text
    session.headers["Referer"] = url

    pks = []
    # 현재 버전은 다운로드 버튼의 onclick 안에, 과거 버전은 data-public-pk 속성에 들어있다
    for pat in (
        r"fn_fileDataDown\(\s*'[^']*'\s*,\s*'(uddi:[^']+)'",
        r'data-public-pk="(uddi:[^"]+)"',
    ):
        for m in re.findall(pat, html):
            if m not in pks:
                pks.append(m)
    return pks


def resolve_file(session: requests.Session, ds_id: str, detail_pk: str) -> tuple[str, str] | None:
    """uddi → (atchFileId, fileDetailSn). publicDataTyCode 가 핵심."""
    r = session.get(
        f"{BASE}/tcs/dss/selectFileDataDownload.do",
        params={
            "publicDataPk": ds_id,
            "publicDataDetailPk": detail_pk,
            "atchFileId": "",
            "fileDetailSn": "1",
            "publicDataTyCode": "PR0051",
        },
        timeout=60,
    )
    try:
        j = r.json()
    except ValueError:
        return None
    if not j.get("status") or not j.get("atchFileId"):
        return None
    return j["atchFileId"], str(j.get("fileDetailSn") or "1")


def download(session: requests.Session, atch_file_id: str, sn: str) -> tuple[str, int] | None:
    """실제 파일을 받아 (파일명, 바이트수) 반환. 서버가 준 원래 파일명을 쓴다."""
    with session.get(
        f"{BASE}/cmm/cmm/fileDownload.do",
        params={"atchFileId": atch_file_id, "fileDetailSn": sn},
        stream=True,
        timeout=(30, 900),
    ) as r:
        r.raise_for_status()
        if "html" in r.headers.get("content-type", "").lower():
            return None

        cd = r.headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd)
        name = unquote(m.group(1)) if m else f"{atch_file_id}.bin"
        dest = OUT_DIR / name

        if dest.exists() and dest.stat().st_size > 0:
            return name, -dest.stat().st_size  # 음수 = 건너뜀 표시

        tmp = dest.with_suffix(dest.suffix + ".part")
        size = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                size += len(chunk)
        tmp.rename(dest)
        return name, size


def fetch_dataset(session: requests.Session, ds_id: str, page_type: str, desc: str, limit: int | None):
    print(f"\n[{ds_id}] {desc}")
    pks = find_detail_pks(session, ds_id, page_type)
    if not pks:
        print("  → uddi를 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있습니다.")
        return
    if limit:
        pks = pks[:limit]
    print(f"  파일 {len(pks)}개 대상")

    for pk in pks:
        resolved = resolve_file(session, ds_id, pk)
        if not resolved:
            print(f"  - {pk[:28]}… 식별자 조회 실패")
            continue
        try:
            got = download(session, *resolved)
        except Exception as exc:
            print(f"  - {pk[:28]}… 다운로드 오류 {type(exc).__name__}")
            continue
        if not got:
            print(f"  - {pk[:28]}… HTML 응답(파일 아님)")
            continue
        name, size = got
        mark = "이미 있음" if size < 0 else "받음"
        print(f"  - {name}  {abs(size) / 1e6:,.1f}MB  {mark}")
        time.sleep(1)  # 포털에 부담 주지 않도록


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = new_session()

    targets = DATASETS
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        targets = [d for d in DATASETS if d[0] in wanted]
        if not targets:  # 등록 안 된 id는 fileData로 가정하고 시도
            targets = [(i, "fileData", "(직접 지정)") for i in sys.argv[1:]]

    for ds_id, page_type, desc in targets:
        try:
            fetch_dataset(session, ds_id, page_type, desc, limit=None)
        except Exception as exc:
            print(f"[{ds_id}] 실패: {type(exc).__name__}: {exc}")

    total = sum(f.stat().st_size for f in OUT_DIR.glob("*") if f.is_file())
    print(f"\n{OUT_DIR} 누적 {total / 1e6:,.0f}MB")


if __name__ == "__main__":
    main()
