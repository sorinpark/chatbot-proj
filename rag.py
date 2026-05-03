from openai import OpenAI
import numpy as np
import json

client = OpenAI(...)

# 이미지 메타데이터 (태그 + 파일명)
IMAGE_DB = [
    {"file": "희종_경계.png", "tags": "차갑고 슬픈 눈빛 경계하는 왕 유배지 불신"},
    {"file": "희종_중립.png", "tags": "조심스러운 표정 마음 열기 시작 유배지"},
    {"file": "희종_신뢰.png", "tags": "신뢰 따뜻한 눈빛 마음 열린 왕"},
    {"file": "희종_감동.png", "tags": "눈물 감동 복위 결심 백성 걱정"},
    {"file": "희종_결의.png", "tags": "결의 복위 의지 강한 눈빛"},
    {"file": "폭군_분노.png", "tags": "분노 위협 광기 폭군"},
    {"file": "폭군_의심.png", "tags": "의심 경계 불쾌 폭군"},
    {"file": "폭군_호탕.png", "tags": "호탕 웃음 기분 좋음 술"},
]

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_best_image(keyword: str) -> str:
    keyword_vec = get_embedding(keyword)
    best_score = -1
    best_file = "희종_중립.png"  # 기본값
    
    for img in IMAGE_DB:
        tag_vec = get_embedding(img["tags"])
        score = cosine_similarity(keyword_vec, tag_vec)
        if score > best_score:
            best_score = score
            best_file = img["file"]
    
    return best_file