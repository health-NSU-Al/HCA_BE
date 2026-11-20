# 참고: RAG — 저장소 만들기와 점수 임계값

- 출처 1: `docs/lectures/02장_RAG_주요코드 구조 및 세부 설명.pdf` — 4단계(임베딩 객체), **6~10단계**(PDF 읽기 → 자르기 → 창고 → FAISS 저장·열기)
- 출처 2: `docs/lectures/RAG_Pipeline_Deconstructed.pdf` — 슬라이드 2(두 단계 흐름), 11~12(프롬프트 틀, `query_rag` 4단계), **13(`query_rag_safe` 임계값)**. 이 PDF는 이미지라 슬라이드를 보고 정리했다.
- 주의: 수업 예제는 한국은행 경제용어 PDF(`econ700.pdf`) 기준이다. 아래 코드는 **우리 프로젝트용으로 줄여 다시 쓴 예시**이고, 숫자(임계값 등)는 우리 문서로 다시 맞춰야 한다.
- 우리 파일: `rag/build_index.py`(만들기, 한 번), `rag/search.py`(질문마다). 규칙은 `.claude/rules/rag.md`.

## 전체 흐름 (RAG_Pipeline 슬라이드 2)

- **Phase 1 사전 준비(한 번)**: PDF → 가위(Chunking) → 숫자 변환(Embedding) → 창고(Vector DB). 수업 6~10단계.
- **Phase 2 질문 처리(질문마다)**: 질문 → Embedding → 검색(Retrieval) → 프롬프트 결합 → LLM → 답. 수업 11~12단계.
- 우리는 Phase 2를 `search_health_docs` **도구**로 만들어 `run_agent`가 호출하게 한다(결정사항.md「기술 스택」).

## 6단계 — PDF 읽기

```python
from langchain_community.document_loaders import PyPDFLoader
pages = PyPDFLoader(path).load_and_split()      # 쪽 단위 Document 리스트
```
- 각 Document = `page_content`(본문) + `metadata`(`source`, `page`, `total_pages`).
- `metadata['page']`는 **0부터** 센다. 사람이 보는 쪽은 `page + 1` → **근거 표시용 쪽수**에 쓴다.

## 7단계 — 500자 가위 (겹침 50)

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(pages)
```
- 문단 → 줄 → 문장 → 글자 순으로 자연스러운 경계에서 자른다.
- **겹침 50**: 문장이 조각 경계에서 잘려도 다음 조각에 문맥이 이어진다(조각 수는 겹침이 있으면 늘어난다).
- 자른 뒤에도 `metadata['page']`가 살아 있어서 출처·쪽수를 표시할 수 있다.
- 10단계: **머리말·목차·판권 쪽은 제외**하고 본문만 넣는다(엉뚱한 근거가 검색에 끼는 것을 막음). 우리도 허가정보 PDF의 표지·목차는 빼는 것을 고려.

## 8단계 — 창고와 검색 (개념 확인용 Chroma)

- `similarity_search(질문, k=3)`: 가장 가까운 조각 3개.
- `similarity_search_with_relevance_scores`: `(조각, 점수)` 쌍. 점수는 클수록 비슷. 예: 0.73 → 0.577 → 0.498. **이 점수를 임계값에 쓴다.**
- 수업은 Chroma를 개념만 보고 **영구 저장은 FAISS로 통일**했다 → 우리도 FAISS.

## 9~10단계 — FAISS 저장과 열기

```python
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3",
                                   encode_kwargs={"normalize_embeddings": True})
MIP = DistanceStrategy.MAX_INNER_PRODUCT        # 정규화 벡터의 내적 = 코사인 유사도

# 만들기 (build_index.py, 한 번)
db = FAISS.from_documents(chunks, embeddings, distance_strategy=MIP)
db.save_local("rag/index")                      # 파일 두 개로 저장

# 열기 (search.py, 임베딩을 다시 하지 않는다)
db = FAISS.load_local("rag/index", embeddings,
                      allow_dangerous_deserialization=True,   # 내가 만든 pkl이라 허용
                      distance_strategy=MIP)
```

핵심
- **저장할 때와 열 때 임베딩 모델이 같아야** 한다(다르면 차원 불일치 오류). `distance_strategy`도 같아야 점수 해석이 같다.
- `index.ntotal`로 벡터 개수 확인. 열 때 임베딩 진행 막대(Batches)가 뜨면 다시 임베딩한 것 → 잘못된 것.
- 수업 4단계 주석: 임베딩은 MiniLM(384차원)에서 `BAAI/bge-m3`로 **그 한 줄만 바꾸면** 품질을 올릴 수 있지만 **창고는 새로 만들어야** 한다. 우리는 처음부터 bge-m3(결정사항.md「기술 스택」).
- 폴더(`rag/index/`)는 `.gitignore`. 팀원은 각자 `python rag/build_index.py`로 만든다.

## 11~12단계 — `query_rag` 4단계 (RAG_Pipeline 슬라이드 11~12)

1. 검색: `retriever.invoke(question)` → 관련 문서 k개
2. 조립: `"\n\n".join(문서 본문)` → Context 덩어리
3. 틀 채우기: 프롬프트 템플릿에 `{context}`, `{question}` 주입. 틀 = 역할 + **규칙("검색 결과에 없는 내용이면 답하지 마세요")** + 변수 자리 2개
4. 생성: LLM 호출 → **최종 답 + 출처(Source)**

12단계 점검: 답이 문서 기반인가, **근거 페이지(Source)가 정확히 매핑되어 출력**되는가. → 우리는 출처 문서명과 쪽수를 답에 반드시 붙인다.

## 응용 2 — `query_rag_safe` 임계값 (RAG_Pipeline 슬라이드 13)

```python
def search_safe(question, threshold=0.4, k=3):
    results = db.similarity_search_with_score(question, k=k)     # (Document, 점수)
    if not results or float(results[0][1]) < threshold:
        return "확인할 수 없어요. 가지고 있는 자료에서 근거를 찾지 못했어요."   # LLM 호출 없이 반환
    ...  # 통과하면 평소 query_rag 흐름
```

- 최고 점수가 **임계값(수업 예: 0.4) 미만**이면 LLM에 보내지 않고 "답변 불가"를 즉시 반환 → 관련 문서가 없을 때 LLM이 지어내는 **환각을 점수 기준으로 사전 차단**.
- 응용 1: `k`는 클수록 속도가 느려지고 답이 산만해지며(컨텍스트 희석), 작으면 정보가 부족하다. 우리는 기획서대로 k=3에서 시작.
- 우리 적용 주의
  - 0.4는 수업 예제의 값이다. **bge-m3 + 우리 허가정보 문서로 "있는 약 / 없는 약" 질문 점수를 직접 찍어 보고** 임계값을 정한다(`config.py`의 임계값 — 권현진 담당 파일이므로 정한 값은 공유). 정한 값과 근거는 `docs/test-log.md`에 남긴다.
  - 점수 방향(클수록 비슷한지)은 사용하는 함수·`distance_strategy`에 따라 다르니 한 번 출력해서 확인한다.
  - 임계값 미만 응답 문구는 상수로 둔다("확인할 수 없어요").
