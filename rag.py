# rag.py
import os
import numpy as np
from openai import OpenAI
import chromadb
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ChromaDB 초기화 (로컬 저장)
chroma_client = chromadb.PersistentClient(path="./chromadb_data")

# 이미지 컬렉션 가져오기 or 생성
collection = chroma_client.get_or_create_collection(
    name="image_collection",
    metadata={"hnsw:space": "cosine"}
)

# 이미지 메타데이터
IMAGE_DB = [
    {"file": "폭군_분노.png", "tags": "폭군 분노 위협 광기 폭군 살기 위험 화남 분개하는 왕"},
    {"file": "폭군_의심.png", "tags": "폭군 의심 경계 불쾌 폭군 눈초리 경계심 불신 냉랭"},
    {"file": "폭군_호탕.png", "tags": "폭군 호탕 웃음 기분 좋음 술 유쾌 흐뭇"},
    {"file": "희종_0.png", "tags": "차갑고 슬픈 눈빛 경계 불신 무기력 유배지 외로움"},
    {"file": "희종_30.png", "tags": "조심스러운 표정 마음 열기 신중 시작 어색함"},
    {"file": "희종_50.png", "tags": "신뢰 따뜻 편안함 친밀 온화"},
    {"file": "희종_70.png", "tags": "눈물 감동 복위 결심 백성 걱정 결의 희망"},
]

def get_embedding(text: str) -> list:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def build_image_db():
    """ChromaDB에 이미지 임베딩 저장 (최초 1회만 실행)"""
    existing = collection.get()
    if len(existing["ids"]) > 0:
        print("이미지 DB 이미 존재함, 스킵")
        return

    print("이미지 DB 구축 중...")
    for i, img in enumerate(IMAGE_DB):
        embedding = get_embedding(img["tags"])
        collection.add(
            ids=[str(i)],
            embeddings=[embedding],
            documents=[img["tags"]],
            metadatas=[{"file": img["file"]}]
        )
    print(f"이미지 DB 구축 완료: {len(IMAGE_DB)}개")

def find_best_image(keyword: str) -> str:
    """키워드로 가장 유사한 이미지 찾기"""
    try:
        keyword_vec = get_embedding(keyword)
        results = collection.query(
            query_embeddings=[keyword_vec],
            n_results=1
        )
        if results["metadatas"] and results["metadatas"][0]:
            return results["metadatas"][0][0]["file"]
    except Exception as e:
        print(f"이미지 검색 오류: {e}")
    
    return "폭군_의심.png"  # 기본값

# 서버 시작 시 자동으로 DB 구축
build_image_db()