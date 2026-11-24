
import streamlit as st
import pandas as pd
import plotly.express as px
import math
from io import BytesIO

# ==========================================
# 1. 웹앱 기본 설정
# ==========================================

st.set_page_config(
    page_title="공유자전거 수요 분석 시스템",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 공유자전거 수요 분석 시스템")

st.write(
    "과거 공유자전거 이용 데이터를 바탕으로 "
    "시간대별·장소별 평균 수요를 분석하고 "
    "적절한 자전거 배치 방향을 제안합니다."
)

st.divider()


# ==========================================
# 2. 데이터 업로드
# ==========================================

st.sidebar.header("📂 데이터 설정")

rental_file = st.sidebar.file_uploader(
    "① 과거 대여 이력 CSV",
    type=["csv"]
)

stock_file = st.sidebar.file_uploader(
    "② 대여소별 자전거 현황 CSV",
    type=["csv"]
)

st.sidebar.caption(
    "두 파일은 아래에 안내된 형식에 맞춰 준비해주세요."
)

if rental_file is None or stock_file is None:

    st.info("분석을 시작하려면 두 개의 CSV 파일을 업로드해주세요.")

    st.subheader("필요한 데이터 형식")

    st.write("**① 과거 대여 이력 데이터**")

    st.dataframe(
        pd.DataFrame({
            "대여일시": [
                "2026-11-01 08:15:00",
                "2026-11-01 08:32:00",
                "2026-11-02 18:20:00"
            ],
            "대여소명": [
                "강남역 1번 출구",
                "강남역 1번 출구",
                "서울역 3번 출구"
            ]
        }),
        use_container_width=True,
        hide_index=True
    )

    st.write("**② 대여소별 자전거 현황 데이터**")

    st.dataframe(
        pd.DataFrame({
            "대여소명": [
                "강남역 1번 출구",
                "서울역 3번 출구"
            ],
            "잔여자전거": [8, 15]
        }),
        use_container_width=True,
        hide_index=True
    )

    st.stop()


# ==========================================
# 3. 데이터 불러오기 및 전처리
# ==========================================

def read_csv_file(file):

    file_bytes = file.getvalue()

    try:
        return pd.read_csv(
            BytesIO(file_bytes),
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:
        return pd.read_csv(
            BytesIO(file_bytes),
            encoding="cp949"
        )


def load_data(rental_file, stock_file):

    rental = read_csv_file(rental_file)
    stock = read_csv_file(stock_file)

    # 필요한 열 확인
    if not {"대여일시", "대여소명"}.issubset(rental.columns):
        raise ValueError(
            "대여 이력 CSV에는 대여일시와 대여소명 열이 필요합니다."
        )

    if not {"대여소명", "잔여자전거"}.issubset(stock.columns):
        raise ValueError(
            "자전거 현황 CSV에는 대여소명과 잔여자전거 열이 필요합니다."
        )

    # 날짜 형식 변환
    rental["대여일시"] = pd.to_datetime(
        rental["대여일시"],
        errors="coerce"
    )

    rental = rental.dropna(
        subset=["대여일시", "대여소명"]
    ).copy()

    # 대여소명 정리
    rental["대여소명"] = (
        rental["대여소명"].astype(str).str.strip()
    )

    stock["대여소명"] = (
        stock["대여소명"].astype(str).str.strip()
    )

    # 자전거 수량 숫자 변환
    stock["잔여자전거"] = pd.to_numeric(
        stock["잔여자전거"],
        errors="coerce"
    )

    stock = stock.dropna(
        subset=["잔여자전거"]
    ).copy()

    if (stock["잔여자전거"] < 0).any():
        raise ValueError("잔여 자전거 수는 음수일 수 없습니다.")

    # 시간대 추출
    rental["시간대"] = rental["대여일시"].dt.hour

    # 날짜 추출
    rental["날짜"] = rental["대여일시"].dt.date

    if rental.empty or stock.empty:
        raise ValueError("분석할 데이터가 부족합니다.")

    # 동일 대여소가 여러 번 등장하면 합산
    stock = (
        stock.groupby("대여소명", as_index=False)
        ["잔여자전거"].sum()
    )

    return rental, stock


try:

    rental, stock = load_data(
        rental_file,
        stock_file
    )

except Exception as e:

    st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
    st.stop()


# ==========================================
# 4. 사용자 분석 조건 선택
# ==========================================

st.sidebar.divider()
st.sidebar.header("🔎 분석 조건 선택")

# 시간대 리스트
hours = list(range(24))

# 대여소 리스트
stations = sorted(
    list(
        set(rental["대여소명"]) &
        set(stock["대여소명"])
    )
)

if not stations:

    st.error(
        "두 CSV 파일에 공통으로 존재하는 대여소가 없습니다."
    )
    st.stop()


selected_hour = st.sidebar.selectbox(
    "분석할 시간대",
    hours,
    index=8,
    format_func=lambda x: f"{x:02d}:00 ~ {x:02d}:59"
)

selected_station = st.sidebar.selectbox(
    "분석할 대여소",
    stations
)

# 수요 대비 확보 비율
safety_rate = st.sidebar.slider(
    "수요 대비 자전거 확보 비율",
    min_value=1.0,
    max_value=1.5,
    value=1.2,
    step=0.1
)

st.sidebar.caption(
    "확보 비율을 1.2로 설정하면 "
    "평균 수요의 120%를 목표 수량으로 계산합니다."
)


# ==========================================
# 5. 평균 수요량 분석 함수
# ==========================================

def analyze_demand(
    rental,
    stock,
    hour,
    station
):

    # 선택한 대여소와 시간대의 기록만 추출
    selected_data = rental[
        (rental["대여소명"] == station) &
        (rental["시간대"] == hour)
    ].copy()

    # 전체 데이터에 포함된 날짜 목록
    all_dates = sorted(
        rental["날짜"].unique()
    )

    # 날짜별 대여 횟수 계산
    daily_counts = (
        selected_data.groupby("날짜")
        .size()
        .reindex(all_dates, fill_value=0)
    )

    # 전체 관측 날짜 기준 평균 수요량
    average_demand = daily_counts.mean()

    # 현재 자전거 수량 확인
    current_bikes = int(
        stock.loc[
            stock["대여소명"] == station,
            "잔여자전거"
        ].sum()
    )

    # 평균 수요에 확보 비율 적용
    target_bikes = math.ceil(
        average_demand * safety_rate
    )

    # 목표 수량과 현재 수량 비교
    difference = target_bikes - current_bikes

    return {
        "평균수요": average_demand,
        "현재자전거": current_bikes,
        "목표수량": target_bikes,
        "차이": difference,
        "분석일수": len(all_dates),
        "날짜별대여량": daily_counts
    }


# ==========================================
# 6. 자전거 배치 가이드 생성 함수
# ==========================================

def make_guide(result):

    demand = result["평균수요"]
    difference = result["차이"]

    if demand == 0:

        return (
            "해당 시간대의 대여 기록이 없습니다. "
            "현재 데이터를 기준으로 추가 배치를 권장하지 않습니다."
        )

    elif difference >= 3:

        return (
            f"자전거 {difference}대를 추가 배치하는 것을 권장합니다."
        )

    elif difference > 0:

        return (
            f"자전거 {difference}대를 추가 배치하는 것이 좋습니다."
        )

    elif difference <= -3:

        return (
            f"자전거 {-difference}대를 다른 대여소로 "
            "이동하는 것을 권장합니다."
        )

    else:

        return (
            "현재 자전거 배치량이 적정 수준입니다. "
            "현재 배치를 유지하는 것을 권장합니다."
        )


# ==========================================
# 7. 선택 조건에 따른 분석 실행
# ==========================================

result = analyze_demand(
    rental,
    stock,
    selected_hour,
    selected_station
)

guide = make_guide(result)


# ==========================================
# 8. 선택 조건 출력
# ==========================================

st.subheader("📍 선택한 분석 조건")

col1, col2 = st.columns(2)

col1.metric(
    "분석 시간대",
    f"{selected_hour:02d}시"
)

col2.metric(
    "분석 대여소",
    selected_station
)

st.caption(
    f"총 {result['분석일수']}일의 과거 데이터를 분석했습니다."
)


# ==========================================
# 9. 주요 분석 결과 출력
# ==========================================

st.divider()

st.subheader("📊 수요 분석 결과")

col1, col2, col3 = st.columns(3)

col1.metric(
    "평균 대여 수요",
    f"{result['평균수요']:.1f}대"
)

col2.metric(
    "현재 잔여 자전거",
    f"{result['현재자전거']}대"
)

col3.metric(
    "권장 확보 수량",
    f"{result['목표수량']}대"
)

st.write(
    f"**평균 수요 대비 확보 비율: {safety_rate:.1f}배**"
)


# ==========================================
# 10. 수요량과 공급량 비교 그래프
# ==========================================

st.divider()

st.subheader("📈 수요량 및 자전거 공급량 비교")

chart_data = pd.DataFrame({
    "항목": [
        "평균 대여 수요",
        "현재 잔여 자전거",
        "권장 확보 수량"
    ],
    "자전거 수량": [
        result["평균수요"],
        result["현재자전거"],
        result["목표수량"]
    ]
})

fig = px.bar(
    chart_data,
    x="항목",
    y="자전거 수량",
    text="자전거 수량",
    title=(
        f"{selected_station} "
        f"{selected_hour:02d}시 수요 분석"
    )
)

fig.update_traces(
    texttemplate="%{text:.1f}",
    textposition="outside"
)

fig.update_layout(
    xaxis_title="",
    yaxis_title="자전거 수량",
    showlegend=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# ==========================================
# 11. 재배치 가이드 출력
# ==========================================

st.divider()

st.subheader("🚲 자전거 재배치 가이드")

if result["평균수요"] == 0:

    st.warning(guide)

elif result["차이"] >= 3:

    st.error("🔴 자전거 부족")
    st.write(guide)

elif result["차이"] > 0:

    st.warning("🟠 추가 배치 권장")
    st.write(guide)

elif result["차이"] <= -3:

    st.info("🔵 자전거 과잉")
    st.write(guide)

else:

    st.success("🟢 적정 배치")
    st.write(guide)


# ==========================================
# 12. 날짜별 평균 대여량 변화
# ==========================================

st.divider()

st.subheader("📅 날짜별 대여량 분석")

daily_chart = pd.DataFrame({
    "날짜": result["날짜별대여량"].index,
    "대여량": result["날짜별대여량"].values
})

fig2 = px.line(
    daily_chart,
    x="날짜",
    y="대여량",
    markers=True,
    title=(
        f"{selected_station} "
        f"{selected_hour:02d}시 날짜별 대여량"
    )
)

fig2.update_layout(
    xaxis_title="날짜",
    yaxis_title="대여 횟수"
)

st.plotly_chart(
    fig2,
    use_container_width=True
)


# ==========================================
# 13. 선택 조건 분석 결과 데이터 출력
# ==========================================

st.divider()

st.subheader("📋 분석 데이터 상세")

output = pd.DataFrame([{
    "시간대": f"{selected_hour:02d}시",
    "대여소명": selected_station,
    "과거 평균 대여량": round(result["평균수요"], 2),
    "현재 잔여 자전거": result["현재자전거"],
    "권장 확보 수량": result["목표수량"],
    "재배치 필요 수량": result["차이"],
    "재배치 가이드": guide
}])

st.dataframe(
    output,
    use_container_width=True,
    hide_index=True
)


# ==========================================
# 14. 분석 결과 다운로드
# ==========================================

st.download_button(
    label="📥 분석 결과 CSV 다운로드",
    data=output.to_csv(
        index=False,
        encoding="utf-8-sig"
    ),
    file_name="공유자전거_수요분석결과.csv",
    mime="text/csv"
)


# ==========================================
# 15. 안내 문구
# ==========================================

st.divider()

st.caption(
    "본 프로그램은 과거 공유자전거 이용 데이터의 "
    "평균값을 활용한 테스트용 수요 분석 시스템입니다."
)

st.caption(
    "현재 잔여 자전거 수는 업로드된 현황 데이터를 사용하며, "
    "재배치 결과는 참고용 권장 수량입니다."
)
