"""소상공인 상가(상권)정보 분기 스냅샷 수집 → 동대문구만 추출.

전국 데이터라 스냅샷 하나가 350MB(ZIP) 수준이고 12개면 4GB가 넘는다.
생활인구와 같은 방식으로 받는 즉시 동대문구 행만 남기고 원본은 지운다.

스냅샷을 여러 시점 모으는 이유는 개·폐업 회전율 때문이다. 이 데이터는
'영업 중인 점포'만 담고 있어서, 두 시점을 비교해야 그 사이에 사라진 점포와
새로 생긴 점포를 알 수 있다.

    uv run python src/download_sangga.py
    uv run python src/download_sangga.py --keep-zip
"""

import csv
import io
import re
import sys
import time
import zipfile
from urllib.parse import unquote

import requests

from config import DATA_INTERIM, DATA_RAW
from download_data_go_kr import BASE, UA, find_detail_pks, resolve_file

DS_ID = "15083033"
ZIP_DIR = DATA_RAW / "sangga"
OUT_DIR = DATA_INTERIM / "sangga_ddm"

DDM_KEYS = ("시군구명", "시군구코드")
DDM_NAME = "동대문구"
DDM_CODE = "11230"  # 상가정보는 행정표준 법정동코드를 쓴다 (집계구 체계와 다름)


def snapshot_date(name: str) -> str:
    """파일명에서 기준일(YYYYMMDD)을 뽑는다."""
    m = re.search(r"(20\d{6})", name)
    return m.group(1) if m else name


def extract_ddm(zip_path, out_path) -> tuple[int, int]:
    kept = total = 0
    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RuntimeError("ZIP 안에 CSV가 없습니다")

        with open(out_path, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            header_written = False

            for member in sorted(members):
                with z.open(member) as fh:
                    stream = io.TextIOWrapper(io.BufferedReader(fh), encoding="utf-8-sig", errors="replace")
                    reader = csv.reader(stream)
                    try:
                        header = next(reader)
                    except StopIteration:
                        continue

                    idx = next((i for i, c in enumerate(header) if c.strip() in DDM_KEYS), None)
                    if idx is None:
                        raise ValueError(f"시군구 컬럼을 찾지 못했습니다: {header[:12]}")

                    if not header_written:
                        writer.writerow(header)
                        header_written = True

                    for row in reader:
                        total += 1
                        if len(row) > idx and (row[idx] == DDM_NAME or row[idx].startswith(DDM_CODE)):
                            writer.writerow(row)
                            kept += 1
    return kept, total


def main():
    keep_zip = "--keep-zip" in sys.argv
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    pks = find_detail_pks(session, DS_ID, "fileData")
    print(f"스냅샷 {len(pks)}개 발견\n")

    started = time.time()
    for i, pk in enumerate(pks, 1):
        resolved = resolve_file(session, DS_ID, pk)
        if not resolved:
            print(f"[{i:>2}/{len(pks)}] 식별자 조회 실패 {pk[:24]}…")
            continue
        atch, sn = resolved

        try:
            with session.get(f"{BASE}/cmm/cmm/fileDownload.do",
                             params={"atchFileId": atch, "fileDetailSn": sn},
                             stream=True, timeout=(30, 900)) as r:
                r.raise_for_status()
                cd = r.headers.get("content-disposition", "")
                m = re.search(r'filename="?([^";]+)"?', cd)
                name = unquote(m.group(1)) if m else f"{atch}.zip"
                date = snapshot_date(name)

                out_path = OUT_DIR / f"sangga_{date}_ddm.csv"
                if out_path.exists() and out_path.stat().st_size > 0:
                    print(f"[{i:>2}/{len(pks)}] {date}  skip (추출 완료)")
                    continue

                zip_path = ZIP_DIR / name
                size = 0
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        size += len(chunk)

            kept, total = extract_ddm(zip_path, out_path)
            if kept == 0:
                out_path.unlink(missing_ok=True)
                raise RuntimeError(f"동대문구 행 0건 (전체 {total:,}) — ZIP 유지")

            if not keep_zip:
                zip_path.unlink(missing_ok=True)
            print(f"[{i:>2}/{len(pks)}] {date}  받기 {size/1e6:,.0f}MB · 동대문구 {kept:,}개 / 전국 {total:,}개"
                  f"   [{(time.time()-started)/60:.0f}분]", flush=True)

        except Exception as exc:
            print(f"[{i:>2}/{len(pks)}] 실패 {type(exc).__name__}: {exc}", flush=True)

    n = len(list(OUT_DIR.glob("*.csv")))
    mb = sum(f.stat().st_size for f in OUT_DIR.glob("*.csv")) / 1e6
    print(f"\n완료: 스냅샷 {n}개 · {mb:,.0f}MB · {(time.time()-started)/60:.0f}분")


if __name__ == "__main__":
    main()
