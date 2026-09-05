"""생활인구(집계구·시간대별)를 행정동 단위 월별 지표로 집계한다.

원본은 10GB가 넘어 통째로 메모리에 올릴 수 없으므로 한 줄씩 흘려보내며 합산한다.

주의할 점 두 가지
  1) 원본의 '행정동코드' 컬럼은 값이 잘못 들어 있다(동대문구 집계구에 강남구 코드).
     대신 집계구코드 앞 7자리가 행정동을 가리키므로 그것을 쓴다.
  2) 3명 이하는 '*'로 마스킹되어 있다. 숫자로 바꿀 수 없는 값은 0으로 처리하되,
     마스킹 건수를 함께 세어 과소집계 정도를 알 수 있게 한다.

산출
  local_people_hourly.csv : 월 × 행정동 × 시간대 평균 생활인구
  local_people_age.csv    : 월 × 행정동 연령대 구성 (야간/주간 구분)

    uv run python src/analyze_local_people.py
"""

import csv
import re
from collections import defaultdict

import pandas as pd

from config import DATA_INTERIM, DATA_PROCESSED

SRC = DATA_INTERIM / "local_people_ddm"

# 집계구코드 앞 7자리 → 행정동명
DONG = {
    "1106071": "회기동", "1106072": "휘경1동", "1106073": "휘경2동",
    "1106080": "청량리동", "1106081": "용신동", "1106082": "제기동",
    "1106083": "전농1동", "1106084": "전농2동", "1106086": "답십리2동",
    "1106087": "장안1동", "1106088": "장안2동", "1106089": "이문1동",
    "1106090": "이문2동", "1106091": "답십리1동",
}
# 청량리 시장 클러스터가 걸쳐 있는 동
CLUSTER = ["청량리동", "제기동", "용신동"]

# 컬럼 위치 (헤더 33개 기준)
I_TIME, I_TOT = 1, 4
MALE = slice(5, 19)    # 남자 0-9 ~ 70+
FEMALE = slice(19, 33)  # 여자 0-9 ~ 70+
# 14개 연령대를 4개 묶음으로: 0~19 / 20~39 / 40~59 / 60+
BANDS = {"0-19": range(0, 3), "20-39": range(3, 7), "40-59": range(7, 11), "60+": range(11, 14)}


def num(v: str) -> float:
    """'*' 마스킹이나 빈 값은 0으로."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def process_file(path):
    """한 달치 파일을 (동, 시간) 합계와 (동, 시간대군, 연령대) 합계로 접는다."""
    hourly = defaultdict(float)                     # (동,시) -> 집계구·일자 합
    ages = defaultdict(lambda: defaultdict(float))  # (동,주야) -> 연령대 -> 합
    days = set()
    masked = total_rows = 0

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            if len(row) < 33:
                continue
            total_rows += 1
            dong = DONG.get(row[3][:7])
            if dong is None:
                continue
            days.add(row[0])
            hour = int(row[I_TIME])
            tot = num(row[I_TOT])
            if row[I_TOT] == "*":
                masked += 1

            hourly[(dong, hour)] += tot

            # 야간(03~05시)은 상주인구, 주간(10~16시)은 활동인구의 대리 지표
            phase = "야간" if 3 <= hour <= 5 else ("주간" if 10 <= hour <= 16 else None)
            if phase:
                m = [num(v) for v in row[MALE]]
                f = [num(v) for v in row[FEMALE]]
                for band, idx in BANDS.items():
                    ages[(dong, phase)][band] += sum(m[i] + f[i] for i in idx)

    return hourly, ages, len(days), masked, total_rows


def main():
    files = sorted(SRC.glob("*.csv"))
    print(f"대상 {len(files)}개월\n")

    h_rows, a_rows = [], []
    masked_all = rows_all = 0

    for i, path in enumerate(files, 1):
        ym = re.search(r"_(\d{6})_", path.name).group(1)
        hourly, ages, n_days, masked, nrows = process_file(path)
        masked_all += masked
        rows_all += nrows
        if n_days == 0:
            continue

        # 합은 (집계구 × 일자)로 쌓였다. 일수로 나누면 '그 동 전체의 시간대별 일평균 인구'.
        for (dong, hour), s in hourly.items():
            h_rows.append({"ym": ym, "dong": dong, "hour": hour, "pop": s / n_days})
        for (dong, phase), bands in ages.items():
            n_hours = 3 if phase == "야간" else 7  # 03~05시 3개, 10~16시 7개
            r = {"ym": ym, "dong": dong, "phase": phase}
            r.update({k: v / n_days / n_hours for k, v in bands.items()})
            a_rows.append(r)

        if i % 20 == 0 or i == len(files):
            print(f"  {i}/{len(files)} 처리 ({ym}, {n_days}일)", flush=True)

    hf = pd.DataFrame(h_rows)
    hf.to_csv(DATA_PROCESSED / "local_people_hourly.csv", index=False)

    af = pd.DataFrame(a_rows)
    af.to_csv(DATA_PROCESSED / "local_people_age.csv", index=False)

    # 요약 출력 — 클러스터 3개 동의 최근 시간대 프로파일
    latest = hf[hf.ym == hf.ym.max()]
    clu = latest[latest.dong.isin(CLUSTER)].pivot_table(
        index="hour", columns="dong", values="pop")
    print(f"\n=== {hf.ym.max()} 시간대별 생활인구 (클러스터 3개 동) ===")
    print(clu.round(0).to_string())

    print(f"\n마스킹('*') {masked_all:,}건 / 전체 {rows_all:,}행 ({masked_all/rows_all*100:.2f}%)")
    print(f"저장: {DATA_PROCESSED}/local_people_hourly_raw.csv, local_people_age_raw.csv")


if __name__ == "__main__":
    main()
