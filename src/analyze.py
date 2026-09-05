"""차트용 집계 데이터를 만든다. 결과는 output/tables/ 에 CSV로 떨어진다.

세 갈래를 처리한다.
  1) 공실 장기 시계열 (2006~2023) — 청량리 클러스터 시장별
  2) 생활인구 시간대·요일·연령 프로파일 — 동대문구 집계구 추출본
  3) 시장 규모·지원이력 등 보조 집계

생활인구 원본은 컬럼이 두 가지로 어긋나 있어 주의가 필요하다.
  - 데이터 행 끝에 빈 필드가 5개 붙어 있어 그냥 읽으면 컬럼이 밀린다 → names 를 명시해 읽는다
  - `행정동코드` 컬럼 값이 실제와 다르다(동대문구 집계구에 강남구 코드가 붙어 있음)
    → 행정동은 `집계구코드` 앞 8자리에서 얻는다
"""

import glob
import re

import pandas as pd

from config import DATA_INTERIM, DATA_RAW, TABLES

VACANCY_DIR = DATA_RAW / "data_go_kr" / "vacancy"
LP_DIR = DATA_INTERIM / "local_people_ddm"

# 청량리 클러스터 시장명 (표기 흔들림을 흡수하려 공백 제거 후 비교)
CLUSTER = [
    "서울약령시장", "경동시장", "청량리청과물시장", "경동광성상가",
    "청량리농수산물시장", "청량리종합시장", "동서시장", "청량리수산시장",
    "청량종합도매시장", "청량리전통시장",
]
CLUSTER_KEYS = {re.sub(r"\s+", "", m) for m in CLUSTER}


def read_korean_csv(path, **kw) -> pd.DataFrame:
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, **kw)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(f"인코딩 판별 실패: {path}")


def pick_col(df, *hints):
    """컬럼명이 연도마다 조금씩 달라서 키워드로 찾는다."""
    for h in hints:
        for c in df.columns:
            if h in str(c).replace(" ", ""):
                return c
    return None


# ---------------------------------------------------------------- 1) 공실 시계열
def vacancy_timeseries() -> pd.DataFrame:
    rows = []
    for path in sorted(glob.glob(str(VACANCY_DIR / "*" / "*.csv"))):
        year = re.search(r"\((\d{4})년\)", path)
        if not year:
            continue
        year = int(year.group(1))

        df = read_korean_csv(path)
        c_name = pick_col(df, "시장명")
        c_open = pick_col(df, "영업점포", "영업점포수")
        c_vac = pick_col(df, "빈점포", "빈점포수")
        c_gu = pick_col(df, "시군구")
        if not (c_name and c_vac):
            print(f"  {year}: 컬럼 인식 실패 — {list(df.columns)[:6]}")
            continue

        df["_key"] = df[c_name].astype(str).str.replace(r"\s+", "", regex=True)
        sub = df[df["_key"].isin(CLUSTER_KEYS)]
        if c_gu is not None:  # 동명이시장 방지
            sub = sub[sub[c_gu].astype(str).str.contains("동대문", na=False)]

        for _, r in sub.iterrows():
            openn = pd.to_numeric(r.get(c_open), errors="coerce") if c_open else None
            vac = pd.to_numeric(r.get(c_vac), errors="coerce")
            total = (openn + vac) if pd.notna(openn) and pd.notna(vac) else None
            rows.append({
                "year": year,
                "market": r["_key"],
                "operating": openn,
                "vacant": vac,
                "total": total,
                "vacancy_rate": round(vac / total * 100, 1) if total else None,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["market", "year"])
        out.to_csv(TABLES / "vacancy_timeseries.csv", index=False)
    return out


# ------------------------------------------------------- 2) 생활인구 프로파일
LP_COLS = [
    "기준일ID", "시간대구분", "행정동코드_원본오류", "집계구코드", "총생활인구수",
    *[f"남자{a}" for a in ["0-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
                           "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+"]],
    *[f"여자{a}" for a in ["0-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
                           "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+"]],
]
AGE_COLS = LP_COLS[5:]


def load_month(path) -> pd.DataFrame:
    """한 달치 추출본을 읽는다. 헤더는 무시하고 명시한 컬럼명을 쓴다."""
    df = pd.read_csv(
        path, skiprows=1, header=None, names=LP_COLS,
        usecols=range(len(LP_COLS)), low_memory=False,
    )
    df["집계구코드"] = df["집계구코드"].astype(str)
    df["행정동"] = df["집계구코드"].str[:8]        # 원본 행정동코드 컬럼은 신뢰 불가
    for c in ["총생활인구수", *AGE_COLS]:
        df[c] = pd.to_numeric(df[c], errors="coerce")  # '*' 마스킹 → NaN
    df["시간"] = pd.to_numeric(df["시간대구분"], errors="coerce")
    df["날짜"] = pd.to_datetime(df["기준일ID"], format="%Y%m%d", errors="coerce")
    return df


def local_people_profiles(months: list[str] | None = None):
    paths = sorted(LP_DIR.glob("*.csv"))
    if months:
        paths = [p for p in paths if any(m in p.name for m in months)]
    if not paths:
        print("생활인구 추출본이 없습니다.")
        return

    hourly, weekday, age, dong, monthly = [], [], [], [], []

    for p in paths:
        ym = re.search(r"(\d{6})", p.name).group(1)
        df = load_month(p)

        # 시간대별 (하루 평균 체류인구)
        h = df.groupby("시간", as_index=False)["총생활인구수"].sum()
        n_days = df["날짜"].nunique()
        h["총생활인구수"] /= max(n_days, 1)
        h["ym"] = ym
        hourly.append(h)

        # 요일별
        w = df.assign(요일=df["날짜"].dt.dayofweek).groupby("요일", as_index=False)["총생활인구수"].sum()
        wd_counts = df.drop_duplicates("날짜").assign(요일=lambda x: x["날짜"].dt.dayofweek)["요일"].value_counts()
        w["총생활인구수"] = w.apply(lambda r: r["총생활인구수"] / max(wd_counts.get(r["요일"], 1), 1), axis=1)
        w["ym"] = ym
        weekday.append(w)

        # 연령·성별 구성 (전체 합)
        a = df[AGE_COLS].sum().rename("인구").reset_index().rename(columns={"index": "구분"})
        a["ym"] = ym
        age.append(a)

        # 행정동별
        d = df.groupby("행정동", as_index=False)["총생활인구수"].sum()
        d["총생활인구수"] /= max(n_days, 1) * 24
        d["ym"] = ym
        dong.append(d)

        monthly.append({"ym": ym, "일평균생활인구": df["총생활인구수"].sum() / max(n_days, 1) / 24})
        print(f"  {ym} 처리 완료 ({n_days}일)")

    pd.concat(hourly).to_csv(TABLES / "lp_hourly.csv", index=False)
    pd.concat(weekday).to_csv(TABLES / "lp_weekday.csv", index=False)
    pd.concat(age).to_csv(TABLES / "lp_age.csv", index=False)
    pd.concat(dong).to_csv(TABLES / "lp_dong.csv", index=False)
    pd.DataFrame(monthly).to_csv(TABLES / "lp_monthly.csv", index=False)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)

    print("=== 1) 공실 장기 시계열 (2006~2023) ===")
    vt = vacancy_timeseries()
    if vt.empty:
        print("  청량리 시장을 찾지 못했습니다.")
    else:
        print(f"  {vt.market.nunique()}개 시장 × {vt.year.nunique()}개 연도 = {len(vt)}행")
        pivot = vt.pivot_table(index="year", columns="market", values="vacancy_rate")
        print(pivot.to_string())

    print("\n=== 2) 생활인구 프로파일 ===")
    local_people_profiles()

    print(f"\n저장 위치: {TABLES}")


if __name__ == "__main__":
    main()
