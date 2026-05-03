
import json
import os

STATE_FILE = "state.json"

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return get_initial_state()

def get_initial_state():
    return {
        "week": 1,
        "호감도": 20,
        "사병수": 50,
        "민심": 100,
        "폭군심기": 60,
        "대화횟수_이번주": 0,
        "연속칭찬횟수": 0,        # 폭군 대화 중 3회 연속 칭찬 체크용
    "미니게임_결과": {
    "협력세력_1차": None,
    "사병키우기_1차": None,
    "비밀서신": None,
    "폭군대화_1차": None,
    "사병키우기_2차": None,
    "사병키우기_3차": None,  # ← 추가
    "협력세력_2차": None,
},
        "conversation_history": []  # GPT에 넘길 대화 기록
    }


# ───────────────────────────────
# 매주 초기화 
# # ───────────────────────────────
def advance_week(state):
    state["week"] += 1
    state["민심"] -= 5           # 매주 민심 -5
    state["대화횟수_이번주"] = 0

    # 이번 주 대화 한 번도 안 했으면 호감도 -5 (주차 넘기기 전에 체크)
    # → advance_week 호출 전에 check_no_conversation() 먼저 호출할 것

    return state


# ───────────────────────────────
# 대화 안 했을 때 패널티 체크
# ───────────────────────────────
def check_no_conversation(state):
    if state["대화횟수_이번주"] == 0:
        state["호감도"] -= 5
    return state


# ───────────────────────────────
# 호감도 변경
# ───────────────────────────────
def update_호감도(state, delta):
    state["호감도"] += delta
    state["호감도"] = max(0, min(100, state["호감도"]))  # 0~100 범위 제한
    return state


# ───────────────────────────────
# 사병 추가
# ───────────────────────────────
def update_사병수(state, count):
    state["사병수"] += count
    return state


# ───────────────────────────────
# 폭군 심기 변경
# ───────────────────────────────
def update_폭군심기(state, delta):
    state["폭군심기"] += delta
    state["폭군심기"] = max(0, min(100, state["폭군심기"]))
    return state


# ───────────────────────────────
# 베드엔딩 조건 체크
# ───────────────────────────────
def check_bad_ending(state):
    if state["호감도"] <= 0:
        return "호감도_0_엔딩"        # 유배지에서 쫓겨남

    if state["민심"] < 60:
        return "민심_부족_엔딩"        # 타임오버

    if state["폭군심기"] <= 0:
        return "폭군_심기_0_엔딩"      # 즉시 나만 죽음

    return None  # 베드엔딩 아님


# ───────────────────────────────
# 최종 성공 조건 체크 (8주차에 호출)
# ───────────────────────────────
def check_success(state):
    all_minigames_success = all(
        v == True for v in state["미니게임_결과"].values()
    )

    if (
        all_minigames_success and
        state["호감도"] >= 90 and
        state["사병수"] >= 1000
    ):
        return "복위_성공_엔딩"

    elif state["호감도"] < 90:
        return "희종_설득_실패_엔딩"  

    elif state["사병수"] < 1000:
        return "사병_부족_엔딩"        # 전장에서 전원 사망

    else:
        return "복위_실패_엔딩"


# ───────────────────────────────
# 미니게임: 협력 세력 선택
# 가/나/다/라 중 1개가 실패 (랜덤으로 매번 달라짐)
# ───────────────────────────────
import random

def minigame_협력세력(state, choice, round_key):
    """
    choice: "가" | "나" | "다" | "라"
    round_key: "협력세력_1차" | "협력세력_2차"
    """
    fail_choice = random.choice(["가", "나", "다", "라"])

    if choice == fail_choice:
        state["미니게임_결과"][round_key] = False
        return state, False, "사약_엔딩"
    else:
        state["미니게임_결과"][round_key] = True
        return state, True, None


# ───────────────────────────────
# 미니게임: 사병 키우기
# 2주차: 300 초과 입력 시 발각
# 5주차: 700 초과 입력 시 발각
# ───────────────────────────────
def minigame_사병키우기(state, count, round_key):
    if round_key == "사병키우기_1차":
        limit = 300
    elif round_key == "사병키우기_2차":
        limit = 700
    else:  # 3차
        limit = 700

    if count > limit:
        state["미니게임_결과"][round_key] = False
        return state, False, "사병_발각_엔딩"
    else:
        state = update_사병수(state, count)
        state["미니게임_결과"][round_key] = True
        return state, True, None

# ───────────────────────────────
# 미니게임: 비밀 서신 전달
# A/B/C/D 중 1개가 실패 (랜덤)
# ───────────────────────────────
def minigame_비밀서신(state, choice):
    """
    choice: "A" | "B" | "C" | "D"
    """
    fail_choice = random.choice(["A", "B", "C", "D"])

    if choice == fail_choice:
        state["미니게임_결과"]["비밀서신"] = False
        return state, False, "사용자&희종_사망_엔딩"
    else:
        state["미니게임_결과"]["비밀서신"] = True
        return state, True, None


# ───────────────────────────────
# 현재 상태 요약 출력 (디버깅용)
# ───────────────────────────────
def print_state(state):
    print(f"""
=== 현재 게임 상태 ===
주차: {state['week']}
호감도: {state['호감도']}
사병수: {state['사병수']}
민심: {state['민심']}
폭군심기: {state['폭군심기']}
이번주 대화횟수: {state['대화횟수_이번주']}
미니게임 결과: {state['미니게임_결과']}
====================
    """)
