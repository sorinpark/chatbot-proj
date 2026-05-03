# main.py
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
from rag import find_best_image
from fastapi.staticfiles import Staticfiles

app.mount("/images", StaticFiles(directory="static/images"), name="images")
from game_state import (
    get_initial_state,
    update_호감도,
    update_사병수,
    update_폭군심기,
    check_bad_ending,
    check_success,
    check_no_conversation,
    advance_week,
    minigame_협력세력,
    minigame_사병키우기,
    minigame_비밀서신,
    save_state,      # ← 추가
    load_state, 
)
from prompt import build_system_prompt, WEEK_NARRATION

# ───────────────────────────────
# 초기 세팅
# ───────────────────────────────
load_dotenv()
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# CORS 설정 (프론트엔드 HTML에서 fetch 할 수 있게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 게임 상태 (서버 메모리에 저장 - 추후 DB로 교체 가능)
game_state = get_initial_state()


# ───────────────────────────────
# 요청/응답 형식 정의
# ───────────────────────────────
class ChatRequest(BaseModel):
    message: str  # 유저가 보낸 메시지

class MinigameRequest(BaseModel):
    type: str    # "협력세력_1차" | "사병키우기_1차" | "비밀서신" 등
    choice: str  # 유저 선택값
class RecommendRequest(BaseModel):
    week: int = 1
    affection: int = 0
    last_npc_text: str = ""

# ───────────────────────────────
# GPT 호출 함수
# ───────────────────────────────
def call_gpt(system_prompt: str, history: list) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        
        response_format={"type": "json_object"}, 
        messages=[
            {"role": "system", "content": system_prompt + " 반드시 JSON 형식으로만 응답하시오."}, 
            *history
        ],
        temperature=0.7
    )

    raw = response.choices[0].message.content
    print("=== GPT RAW 응답 ===")
    print(raw)
    print("====================")

    clean = raw.strip().replace("```json", "").replace("```", "").strip()
    clean = re.sub(r':\s*\+(\d)', r': \1', clean)

    # JSON 없이 텍스트만 온 경우
    if not clean.startswith("{") and not clean.startswith("["):
        return {
            "대사": clean[:150],
            "호감도변화": 0,
            "심기변화": 0,
            "이유": "텍스트 응답",
            "추천답변": ["계속 말씀해 주시오.", "전하, 괜찮으십니까?", "함께하겠습니다."],
            "이미지키워드": "유배지 왕",
            "힌트": None
        }

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            parsed = parsed[0]
        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        # 대사 안에 JSON이 끼어있으면 제거
        if "대사" in parsed:
            대사 = parsed["대사"]
            for marker in ['{"', '{ "', "{ '", "{'}"]:
                brace_idx = 대사.find(marker)
                if brace_idx > 0:
                    parsed["대사"] = 대사[:brace_idx].strip()
                    break

        return parsed

    except json.JSONDecodeError:
        대사_match = re.search(r'"대사"\s*:\s*"([^"]+)"', clean)
        호감도_match = re.search(r'"호감도변화"\s*:\s*([+-]?\d+)', clean)
        추천_match = re.search(r'"추천답변"\s*:\s*\[([^\]]+)\]', clean)
        추천답변 = ["다시 말씀해 주시오.", "전하, 괜찮으십니까?", "함께하겠습니다."]
        if 추천_match:
            items = re.findall(r'"([^"]+)"', 추천_match.group(1))
            if len(items) >= 3:
                추천답변 = items[:3]
        대사 = 대사_match.group(1) if 대사_match else clean[:100]
        return {
            "대사": 대사,
            "호감도변화": int(호감도_match.group(1)) if 호감도_match else 0,
            "심기변화": 0,
            "이유": "파싱 오류",
            "추천답변": 추천답변,
            "이미지키워드": "유배지 왕",
            "힌트": None
        }
@app.post("/recommend")
def recommend(req: RecommendRequest):
    prompt = f"""조선시대 궁중 게임에서 플레이어가 폐위된 왕 희종에게 할 수 있는 추천 답변 5개를 만들어줘.
조건: {req.week}주차, 호감도={req.affection}, 희종의 마지막 말="{req.last_npc_text}".
각 답변은 자연스러운 한국어 1문장(20자 이내).
반드시 JSON 배열로만: ["답변1","답변2","답변3","답변4","답변5"]. JSON 외 절대 없이."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    raw = response.choices[0].message.content
    clean = raw.strip().replace("```json","").replace("```","").strip()
    try:
        parsed = json.loads(clean)
        return {"추천답변": parsed}
    except:
        return {"추천답변": ["전하, 안녕하십니까.", "걱정 마시옵소서.", "함께하겠습니다.", "백성들이 기다리오.", "힘내시길 바라오."]}

# ───────────────────────────────
# 엔드포인트 1: 서버 상태 확인
# ───────────────────────────────
@app.get("/")
def root():
    return {"message": "단종 프로젝트 서버 살아있음!"}


# ───────────────────────────────
# 엔드포인트 2: 게임 상태 조회
# ───────────────────────────────
@app.get("/state")
def get_state():
    return {
        "week": game_state["week"],
        "호감도": game_state["호감도"],
        "사병수": game_state["사병수"],
        "민심": game_state["민심"],
        "폭군심기": game_state["폭군심기"],
        "대화횟수_이번주": game_state["대화횟수_이번주"],
        "미니게임_결과": game_state["미니게임_결과"],
    }


# ───────────────────────────────
# 엔드포인트 3: 게임 초기화
# ───────────────────────────────
@app.post("/reset")
def reset_game():
    global game_state
    game_state = get_initial_state()
    return {"message": "게임이 초기화되었습니다.", "state": game_state}


# ───────────────────────────────
# 엔드포인트 4: 일반 대화 (핵심!)
# ───────────────────────────────


@app.post("/chat")
def chat(req: ChatRequest):
    global game_state

    # 1. 유저 메시지 추가 및 횟수 증가
    game_state["conversation_history"].append({"role": "user", "content": req.message})
    game_state["대화횟수_이번주"] += 1

    # 2. 시스템 프롬프트 생성 및 GPT 호출
    system_prompt = build_system_prompt(game_state)
    gpt_response = call_gpt(system_prompt, game_state["conversation_history"])

    # 3. GPT 응답 추가 및 스탯 업데이트
    game_state["conversation_history"].append({
        "role": "assistant", 
        "content": gpt_response.get("대사", "")
    })
    
    호감도_변화 = gpt_response.get("호감도변화", 0)
    game_state = update_호감도(game_state, 호감도_변화)

    # 4. 주차 전환 여부 판단 (플래그만 먼저 설정)
    week_advanced = False
    current_week_for_ui = game_state["week"] # 현재 주차를 변수에 저장
    
    if game_state["대화횟수_이번주"] >= 5:
        week_advanced = True
        # 주차를 넘기기 전 상태에서 나레이션을 가져옴
        next_week_narration = WEEK_NARRATION.get(current_week_for_ui + 1, "")
        
        # 5. 실제 데이터 업데이트 (응답에 담을 변수들을 다 만든 후 실행)
        game_state = check_no_conversation(game_state)
        game_state = advance_week(game_state) # 여기서 실제 week가 +1 됨
    else:
        next_week_narration = None

    # 6. 베드엔딩 및 성공 체크
    bad_ending = check_bad_ending(game_state)
    success_result = None
    if game_state["week"] > 8:
        success_result = check_success(game_state)

    save_state(game_state)


    이미지키워드 = gpt_response.get("이미지키워드", "")
    best_image = find_best_image(이미지키워드)
    # 7. 응답 반환 (UI에는 현재 주차와 GPT 답변을 함께 보냄)
    return {
        "대사": gpt_response.get("대사", ""),
        "추천답변": gpt_response.get("추천답변", []),
        "이미지키워드": gpt_response.get("이미지키워드", ""),
        "이미지파일": best_image,
        "best_image": best_image,   
           "stats": {
        "호감도": game_state["호감도"],
        "호감도변화": 호감도_변화,
        "사병수": game_state["사병수"],
        "민심": game_state["민심"],
        "폭군심기": game_state["폭군심기"],
        "폭군심기변화": gpt_response.get("심기변화", 0),  # ← 추가
        "week": game_state["week"],
           },
        "week_advanced": week_advanced,
        "narration": next_week_narration,
        "bad_ending": bad_ending,
        "success_result": success_result,
    }

# ───────────────────────────────
# 엔드포인트 5: 미니게임 처리
# ───────────────────────────────
@app.post("/minigame")
def minigame(req: MinigameRequest):
    global game_state

    result = None
    ending = None
    success = False

    # 협력세력 선택 (1차 / 2차)
    if req.type in ["협력세력_1차", "협력세력_2차"]:
        game_state, success, ending = minigame_협력세력(
            game_state, req.choice, req.type
        )

    # 사병 키우기 (1차 / 2차 / 3차)
    elif req.type in ["사병키우기_1차", "사병키우기_2차", "사병키우기_3차"]:
        try:
            count = int(req.choice)
        except ValueError:
            return {"error": "숫자를 입력해주세요."}
        game_state, success, ending = minigame_사병키우기(
            game_state, count, req.type
    )

    # 비밀 서신 전달
    elif req.type == "비밀서신":
        game_state, success, ending = minigame_비밀서신(
            game_state, req.choice
        )

    else:
        return {"error": "알 수 없는 미니게임 타입"}

    return {
    "success": success,
    "ending": ending,
    "game_over": not success,  # ← 이거 추가
    "stats": {
        "사병수": game_state["사병수"],
        "호감도": game_state["호감도"],
        "민심": game_state["민심"],
    },
    "미니게임_결과": game_state["미니게임_결과"],
}


# ───────────────────────────────
# 엔드포인트 6: 주차 전환 (폭군 씬 진입)
# ───────────────────────────────
@app.post("/tyrant/start")
def start_tyrant_scene():
    global game_state
    game_state["폭군_대화중"] = True
    game_state["폭군심기"] = 60 if game_state["week"] == 4 else 40
    game_state["연속칭찬횟수"] = 0
    return {"message": "폭군과의 대화 시작", "심기": game_state["폭군심기"]}


@app.post("/tyrant/end")
def end_tyrant_scene():
    global game_state
    game_state["폭군_대화중"] = False
    return {"message": "폭군과의 대화 종료"}