"""서울시 집계구 단위 생활인구(내국인) OA-14979 — 다운로드 후 동대문구만 추출.

2026-07-31자로 생산 종료 공지가 있어 과거 파일 확보가 목적이다.
제공 범위: 2017-01 ~ 2026-07 (115개월). 월 ZIP이 약 1.2GB, 전체로는 약 138GB이므로
원본을 그대로 쌓지 않고 아래 순서로 처리한다.

    받기 → ZIP 안의 일별 CSV를 스트리밍하며 동대문구(집계구코드 11230*) 행만 남김
         → 월별 CSV 한 개로 저장 → 원본 ZIP 삭제

이렇게 하면 최종 용량이 수 GB 수준으로 줄어든다. 대신 나중에 다른 자치구가 필요해지면
다시 받아야 하는데, 종료 공지 때문에 그때는 못 받을 수 있다는 점은 감수한 선택이다.

중단해도 안전하다. 이미 추출된 달은 건너뛴다.

사용:
    uv run python src/download_local_people.py             # 전체 (약 40시간)
    uv run python src/download_local_people.py 2201 2607   # 구간 지정
    uv run python src/download_local_people.py --keep-zip  # 원본도 보관
"""

import csv
import io
import sys
import time
import zipfile

import requests

from config import DATA_INTERIM, DATA_RAW

INF_ID = "OA-14979"
REFERER = f"https://data.seoul.go.kr/dataList/{INF_ID}/F/1/datasetView.do"
DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

ZIP_DIR = DATA_RAW / "local_people"
OUT_DIR = DATA_INTERIM / "local_people_ddm"

# 집계구코드는 통계청(SGIS) 시군구 코드 체계를 쓴다. 행정표준코드와 다르므로 주의:
#   행정표준코드 동대문구 = 11230  /  통계청 코드 동대문구 = 11060 (11230은 강남구)
# 이걸 혼동하면 엉뚱한 자치구를 추출하게 된다. SGIS addr/stage API로 확인한 값이다.
DDM_PREFIX = "11060"
GU_COL_HINTS = ("집계구코드", "TOT_REG_CD", "집계구")

# 집계구코드 앞 8자리 = 행정동코드. 원본의 '행정동코드' 컬럼도 같은 값을 담고 있다.
MARKET_DONGS = {
    "11060820": "제기동",    # 서울약령시, 경동시장, 경동광성상가, 청량종합도매시장
    "11060800": "청량리동",  # 청량리종합·농수산물·청과물·동서·전통시장
    "11060810": "용신동",    # 청량리수산시장
    "11060830": "전농1동",
    "11060840": "전농2동",
}
TIMEOUT = (30, 600)  # (연결, 각 chunk 읽기) — 총 시간 제한이 아니므로 대용량도 안전


def all_seqs() -> list[str]:
    seqs = []
    for year in range(17, 27):
        for month in range(1, 13):
            if year == 26 and month > 7:
                break
            seqs.append(f"{year:02d}{month:02d}")
    return seqs


def sniff_encoding(zip_path) -> str:
    """ZIP 안 첫 CSV의 헤더로 인코딩을 판별한다. 실측상 CP949지만 바뀔 수 있어 매번 확인."""
    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in sorted(z.namelist()) if n.lower().endswith(".csv"))
        with z.open(member) as fh:
            head = fh.read(4096)

    for enc in ("cp949", "utf-8-sig", "utf-8"):
        try:
            text = head.decode(enc)
        except UnicodeDecodeError:
            continue
        if any(hint in text for hint in GU_COL_HINTS):
            return enc
    raise ValueError("인코딩을 판별하지 못했습니다 (집계구코드 컬럼을 못 찾음)")


def find_gu_column(header: list[str]) -> int:
    for i, name in enumerate(header):
        if any(h in name for h in GU_COL_HINTS):
            return i
    raise ValueError(f"집계구코드 컬럼을 찾지 못했습니다. 헤더: {header[:8]}")


def extract_ddm(zip_path, out_path) -> tuple[int, int]:
    """ZIP 안의 일별 CSV에서 동대문구 행만 뽑아 하나의 CSV로 만든다.

    반환: (남긴 행 수, 전체 읽은 행 수)
    """
    kept = total = 0
    header_written = False
    encoding = sniff_encoding(zip_path)

    with zipfile.ZipFile(zip_path) as z, open(out_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        members = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))

        for member in members:
            with z.open(member) as fh:
                reader = csv.reader(io.TextIOWrapper(io.BufferedReader(fh), encoding=encoding, errors="replace"))
                try:
                    header = next(reader)
                except StopIteration:
                    continue

                gu_idx = find_gu_column(header)
                if not header_written:
                    writer.writerow(header)
                    header_written = True

                for row in reader:
                    total += 1
                    if len(row) > gu_idx and row[gu_idx].startswith(DDM_PREFIX):
                        writer.writerow(row)
                        kept += 1

    return kept, total


def download_zip(seq: str, session: requests.Session, dest) -> int:
    """월별 ZIP을 받는다. Content-Length와 대조해 잘린 파일을 걸러낸다."""
    with session.post(
        DOWNLOAD_URL,
        data={"infId": INF_ID, "seqNo": "", "seq": seq, "infSeq": "1"},
        timeout=TIMEOUT,
        stream=True,
    ) as resp:
        resp.raise_for_status()
        if "html" in resp.headers.get("content-type", "").lower():
            raise RuntimeError("HTML 응답 — 파일이 아닙니다")

        expected = int(resp.headers.get("content-length") or 0)
        tmp = dest.with_suffix(".part")
        size = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                size += len(chunk)

        if expected and size != expected:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"불완전 다운로드 {size:,}/{expected:,} bytes")

        tmp.rename(dest)
        return size


def process(seq: str, session: requests.Session, keep_zip: bool) -> str:
    out_path = OUT_DIR / f"LOCAL_PEOPLE_20{seq}_ddm.csv"
    if out_path.exists() and out_path.stat().st_size > 0:
        return f"skip   ({out_path.stat().st_size / 1e6:,.1f}MB 추출 완료)"

    zip_path = ZIP_DIR / f"LOCAL_PEOPLE_20{seq}.zip"
    dl_note = "재사용"
    if not zip_path.exists():
        size = download_zip(seq, session, zip_path)
        dl_note = f"{size / 1e6:,.0f}MB"

    tmp_out = out_path.with_suffix(".part")
    try:
        kept, total = extract_ddm(zip_path, tmp_out)
    except Exception:
        tmp_out.unlink(missing_ok=True)
        raise

    if kept == 0:
        tmp_out.unlink(missing_ok=True)
        raise RuntimeError(
            f"동대문구({DDM_PREFIX}*) 행이 0건입니다. 집계구코드 형식을 확인하세요. "
            f"(전체 {total:,}행) — ZIP은 삭제하지 않았습니다"
        )

    tmp_out.rename(out_path)
    if not keep_zip:
        zip_path.unlink(missing_ok=True)

    pct = kept / total * 100 if total else 0
    return f"OK     받기 {dl_note} · 추출 {kept:,}행 / 전체 {total:,}행 ({pct:.2f}%)"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep_zip = "--keep-zip" in sys.argv

    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    seqs = all_seqs()
    if len(args) == 2:
        seqs = [s for s in seqs if args[0] <= s <= args[1]]

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": REFERER})

    print(f"대상 {len(seqs)}개월 ({seqs[0]} ~ {seqs[-1]})")
    print(f"  ZIP 임시    : {ZIP_DIR}" + ("" if keep_zip else "  (추출 후 삭제)"))
    print(f"  추출 결과   : {OUT_DIR}\n")

    failed = []
    started = time.time()

    for i, seq in enumerate(seqs, 1):
        label = f"[{i:>3}/{len(seqs)}] 20{seq[:2]}-{seq[2:]}"
        try:
            result = process(seq, session, keep_zip)
        except Exception as exc:
            result = f"FAIL   {type(exc).__name__}: {exc}"
            failed.append(seq)

        elapsed = (time.time() - started) / 60
        print(f"{label}  {result}   [{elapsed:.0f}분 경과]", flush=True)

    total_mb = sum(f.stat().st_size for f in OUT_DIR.glob("*.csv")) / 1e6
    print(f"\n완료 {len(seqs) - len(failed)}/{len(seqs)} · 추출본 {total_mb:,.0f}MB · {(time.time() - started) / 3600:.1f}시간")
    if failed:
        print(f"실패 {len(failed)}개: {', '.join(failed)}")
        print("→ 같은 명령을 다시 실행하면 실패분만 재시도합니다.")


if __name__ == "__main__":
    main()
