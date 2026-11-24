
import streamlit as st
import math

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="공유자전거 수요 분석 시스템",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 공유자전거 수요 분석 시스템")

st.markdown(
    """
    시간대별·장소별 평균 대여 수요를 분석하여
    대여소별 적정 자전거 배치량을 안내하는 시스템입니다.
    """
)

st.info(
    "현재 데이터는 서비스 시연을 위해 구성한 가상 예시 데이터입니다. "
    "실제 공공자전거 운영 통계와는 구분됩니다."
)

# ==========================================
# 2. 내장 데이터
# ==========================================

stations = {
    "강남역 1번 출구": {
        "type": "출퇴근 중심형",
        "bikes": 20,
        "demand": [
            1, 0, 0, 0, 1, 3, 12, 28,
            19, 10, 8, 9, 11, 12, 10, 12,
            16, 23, 31, 24, 14, 8, 5, 3
        ]
    },

    "잠실역 2번 출구": {
        "type": "복합 생활형",
        "bikes": 18,
        "demand": [
            1, 0, 0, 0, 0, 2, 8, 17,
            14, 9, 8, 10, 13, 15, 14, 16,
            20, 25, 28, 22, 14, 8, 4, 2
        ]
    },

    "여의나루역 1번 출구": {
        "type": "여가·관광형",
        "bikes": 25,
        "demand": [
            0, 0, 0, 0, 0, 1, 5, 13,
            12, 16, 22, 28, 32, 35, 31, 28,
            24, 20, 14, 8, 4, 2, 1, 0
        ]
    },

    "홍대입구역 3번 출구": {
        "type": "상업·유동인구형",
        "bikes": 22,
        "demand": [
            1, 0, 0, 0, 1, 2, 7, 14,
            18, 16, 17, 19, 21, 22, 24, 25,
            27, 30, 33, 29, 22, 15, 8, 3
        ]
    },

    "시청역 5번 출구": {
        "type": "업무지구형",
        "bikes": 16,
        "demand": [
            0, 0, 0, 0, 0, 1, 9, 22,
            18, 9, 7, 8, 9, 8, 7, 9,
            15, 24, 29, 18, 9, 4, 2, 1
        ]
    }
}


# ==========================================
# 3. 수요 분석 함수
# ==========================================

def analyze_demand(station, hour, safety_rate):

    station_data = stations[station]

    average_demand = station_data["demand"][hour]
    current_bikes = station_data["bikes"]

    target_bikes = math.ceil(
        average_demand * safety_rate
    )

    difference = target_bikes - current_bikes

    return {
        "average": average_demand,
        "current": current_bikes,
        "target": target_bikes,
        "difference": difference
    }


# ==========================================
# 4. 배치 가이드 함수
# ==========================================

def make_guide(result):

    difference = result["difference"]
    demand = result["average"]

    if demand == 0:
        return (
            "수요 없음",
            "해당 시간대의 예상 대여 수요가 없습니다.",
            "info"
        )

    elif difference >= 3:
        return (
            "자전거 추가 배치 권장",
            f"현재보다 자전거 {difference}대를 추가 배치하는 것이 권장됩니다.",
            "error"
        )

    elif difference > 0:
        return (
            "소량 추가 배치 권장",
            f"자전거 {difference}대를 추가 배치하는 것이 권장됩니다.",
            "warning"
        )

    elif difference <= -3:
        return (
            "자전거 감축 및 재배치 권장",
            f"자전거 {-difference}대를 다른 대여소로 이동하는 것이 권장됩니다.",
            "info"
        )

    else:
        return (
            "현재 배치 유지",
            "현재 자전거 보유량이 적정 수준입니다.",
            "success"
        )


# ==========================================
# 5. 분석 조건 선택
# ==========================================

st.sidebar.header("🔎 분석 조건 설정")

selected_station = st.sidebar.selectbox(
    "대여소 선택",
    list(stations.keys())
)

selected_hour = st.sidebar.selectbox(
    "분석 시간대 선택",
    list(range(24)),
    format_func=lambda hour: (
        f"{hour:02d}:00 ~ {(hour + 1) % 24:02d}:00"
    )
)

st.sidebar.divider()

st.sidebar.subheader("현재 자전거 보유량")

current_bikes = stations[selected_station]["bikes"]

st.sidebar.metric(
    "내장된 자전거 보유량",
    f"{current_bikes}대"
)

safety_rate = st.sidebar.slider(
    "수요 대비 여유 배치 비율",
    min_value=1.0,
    max_value=1.5,
    value=1.2,
    step=0.1
)


# ==========================================
# 6. 분석 실행
# ==========================================

result = analyze_demand(
    selected_station,
    selected_hour,
    safety_rate
)

guide_title, guide_description, guide_type = make_guide(result)


# ==========================================
# 7. 선택 조건 표시
# ==========================================

st.divider()

st.subheader("📍 분석 대상")

col1, col2, col3 = st.columns(3)

with col1:
    st.write("**선택 대여소**")
    st.write(selected_station)

with col2:
    st.write("**대여소 유형**")
    st.write(stations[selected_station]["type"])

with col3:
    st.write("**분석 시간대**")
    st.write(
        f"{selected_hour:02d}:00 ~ "
        f"{(selected_hour + 1) % 24:02d}:00"
    )


# ==========================================
# 8. 주요 분석 결과
# ==========================================

st.divider()

st.subheader("📊 수요 분석 결과")

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        "평균 예상 대여 수요",
        f"{result['average']}대"
    )

with metric2:
    st.metric(
        "현재 자전거 보유량",
        f"{result['current']}대"
    )

with metric3:
    st.metric(
        "권장 자전거 배치량",
        f"{result['target']}대",
        delta=f"{result['difference']:+d}대"
    )


# ==========================================
# 9. 배치 가이드 출력
# ==========================================

st.divider()

st.subheader("🚲 자전거 배치 가이드")

if guide_type == "error":
    st.error(guide_title)
elif guide_type == "warning":
    st.warning(guide_title)
elif guide_type == "success":
    st.success(guide_title)
else:
    st.info(guide_title)

st.write(guide_description)

st.caption(
    f"수요 대비 여유 배치 비율: {safety_rate:.1f}"
)


# ==========================================
# 10. 선택 대여소의 시간대별 수요
# ==========================================

st.divider()

st.subheader("📈 시간대별 평균 수요 분석")

hourly_demand = stations[selected_station]["demand"]

hour_labels = [
    f"{hour:02d}시"
    for hour in range(24)
]

hourly_chart = {
    "평균 대여 수요": hourly_demand
}

st.bar_chart(hourly_chart)

st.caption(
    "선택한 대여소의 0시부터 23시까지 시간대별 평균 대여 수요입니다."
)


# ==========================================
# 11. 동일 시간대 대여소별 수요 비교
# ==========================================

st.divider()

st.subheader("📍 대여소별 수요 비교")

comparison_data = {}

for station in stations:

    comparison_data[station] = (
        stations[station]["demand"][selected_hour]
    )

st.bar_chart(comparison_data)

st.caption(
    f"{selected_hour:02d}시 기준 대여소별 평균 수요 비교"
)


# ==========================================
# 12. 전체 시간대 상세 데이터
# ==========================================

st.divider()

st.subheader("📋 시간대별 상세 데이터")

detail_data = []

for hour in range(24):

    detail_data.append({
        "시간대": f"{hour:02d}:00",
        "평균 예상 대여량": hourly_demand[hour],
        "현재 보유량": current_bikes,
        "권장 배치량": math.ceil(
            hourly_demand[hour] * safety_rate
        )
    })

st.dataframe(
    detail_data,
    use_container_width=True,
    hide_index=True
)


# ==========================================
# 13. 시스템 안내
# ==========================================

st.divider()

st.subheader("ℹ️ 분석 시스템 안내")

st.markdown(
    """
    **데이터 구성**
    - 대여소별 시간대 평균 대여 수요
    - 대여소별 현재 자전거 보유량
    - 대여소 유형별 수요 패턴

    **분석 방식**
    - 선택한 시간대의 평균 수요량 확인
    - 현재 보유량과 권장 배치량 비교
    - 수요량에 따라 자전거 추가·감축·유지 판단

    **데이터 관련 유의사항**
    - 현재 데이터는 시연을 위한 가상 데이터입니다.
    - 실시간 자전거 위치나 실제 재고를 반영하지 않습니다.
    - 실제 운영에 적용하려면 공공자전거 실측 데이터로 교체해야 합니다.
    """
)

st.caption(
    "공유자전거 시간대별·장소별 수요 분석 시스템"
)
