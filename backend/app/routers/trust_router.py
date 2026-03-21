"""
Trust / Health endpoints:
  GET  /business/snapshot       — KB fill stats + document counts
  POST /business/test/generate  — generate 5 quiz questions from KB
  POST /business/test/score     — score user answers vs. buddy's KB knowledge
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.database import get_db
from app.models import User, KnowledgeBase, Document
from app.auth import get_current_user
from app.knowledge import KB_CATEGORIES
from app.llm import call_llm
from app.schemas import (
    HealthSnapshotResponse,
    TestGenerateResponse, TestQuestion,
    TestScoreRequest, TestScoreResponse, TestResultItem,
)

router = APIRouter(prefix="/business", tags=["trust"])


@router.get("/snapshot", response_model=HealthSnapshotResponse)
async def get_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    biz_id = current_user.business_id

    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == biz_id)
    )
    kb = kb_result.scalar_one_or_none()
    kb_data = kb.data if kb else {}
    phase   = kb.phase if kb else "discovery"

    filled   = [c for c in KB_CATEGORIES if kb_data.get(c)]
    missing  = [c for c in KB_CATEGORIES if not kb_data.get(c)]
    fill_pct = round(len(filled) / len(KB_CATEGORIES) * 100, 1)

    # Document count
    doc_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.business_id == biz_id, Document.status == "done")
    )
    total_docs = doc_result.scalar() or 0

    # Chunk count (raw SQL — pgvector table)
    try:
        chunk_result = await db.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE business_id = :bid"),
            {"bid": str(biz_id)},
        )
        total_chunks = chunk_result.scalar() or 0
    except Exception:
        total_chunks = 0

    return HealthSnapshotResponse(
        kb_fill_pct=fill_pct,
        filled_categories=filled,
        missing_categories=missing,
        phase=phase,
        total_documents=total_docs,
        total_chunks=total_chunks,
    )


@router.post("/test/generate", response_model=TestGenerateResponse)
async def generate_test(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    biz_id = current_user.business_id

    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == biz_id)
    )
    kb = kb_result.scalar_one_or_none()
    kb_data = kb.data if kb else {}
    filled  = [c for c in KB_CATEGORIES if kb_data.get(c)]

    if len(filled) < 3:
        raise HTTPException(
            status_code=400,
            detail="Not enough knowledge yet. Keep chatting until at least 3 categories are filled.",
        )

    kb_summary = "\n".join(
        f"{cat}: {json.dumps(kb_data[cat])}" for cat in filled
    )

    prompt = f"""You are testing whether a user knows their own business as well as the AI does.

Here is the AI's knowledge base about this business:
{kb_summary}

Generate exactly 5 quiz questions that test factual knowledge of this specific business.
Each question should have a clear, specific answer found in the knowledge base above.
Cover different categories — don't repeat topics.

Return ONLY valid JSON in this exact format:
{{
  "questions": [
    {{"id": 1, "question": "...", "category": "<category_name>"}},
    {{"id": 2, "question": "...", "category": "<category_name>"}},
    {{"id": 3, "question": "...", "category": "<category_name>"}},
    {{"id": 4, "question": "...", "category": "<category_name>"}},
    {{"id": 5, "question": "...", "category": "<category_name>"}}
  ]
}}"""

    try:
        raw = call_llm(
            system=None,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            use_doc_model=True,
        )
    except Exception as e:
        msg = str(e)
        if "rate_limit" in msg.lower() or "rate limit" in msg.lower() or "429" in msg:
            raise HTTPException(status_code=429, detail="Rate limit hit — wait a few seconds and try again.")
        raise HTTPException(status_code=502, detail=f"LLM error: {msg}")

    try:
        import re
        text_clean = raw.strip()
        text_clean = re.sub(r"^```json\s*", "", text_clean)
        text_clean = re.sub(r"```\s*$", "", text_clean).strip()
        data = json.loads(text_clean)
        questions = [TestQuestion(**q) for q in data["questions"]]
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to parse LLM response into questions")

    return TestGenerateResponse(questions=questions)


@router.post("/test/score", response_model=TestScoreResponse)
async def score_test(
    body: TestScoreRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    biz_id = current_user.business_id

    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == biz_id)
    )
    kb = kb_result.scalar_one_or_none()
    kb_data = kb.data if kb else {}

    kb_summary = "\n".join(
        f"{cat}: {json.dumps(kb_data[cat])}"
        for cat in KB_CATEGORIES if kb_data.get(cat)
    )

    answer_map = {a.question_id: a.answer for a in body.answers}

    qa_pairs = "\n".join(
        f"Q{q.id}: {q.question}\nUser answer: {answer_map.get(q.id, '(no answer)')}"
        for q in body.questions
    )

    prompt = f"""You are evaluating how well a user knows their own business.

KNOWLEDGE BASE (ground truth):
{kb_summary}

USER'S ANSWERS TO QUIZ:
{qa_pairs}

For each question, score the user's answer 1-5 based on accuracy vs. the knowledge base:
5 = completely correct
4 = mostly correct, minor gaps
3 = partially correct
2 = mostly wrong but shows some understanding
1 = wrong or blank

Return ONLY valid JSON:
{{
  "results": [
    {{
      "question_id": 1,
      "question": "<repeat the question>",
      "your_answer": "<user's answer>",
      "buddy_answer": "<the correct answer from the KB>",
      "score": 4,
      "feedback": "<1 sentence explanation>"
    }}
  ],
  "overall_score": 3.8,
  "summary": "<2-3 sentence overall assessment>"
}}"""

    try:
        raw = call_llm(
            system=None,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            use_doc_model=True,
        )
    except Exception as e:
        msg = str(e)
        if "rate_limit" in msg.lower() or "rate limit" in msg.lower() or "429" in msg:
            raise HTTPException(status_code=429, detail="Rate limit hit — wait a few seconds and try again.")
        raise HTTPException(status_code=502, detail=f"LLM error: {msg}")

    try:
        import re
        text_clean = raw.strip()
        text_clean = re.sub(r"^```json\s*", "", text_clean)
        text_clean = re.sub(r"```\s*$", "", text_clean).strip()
        data = json.loads(text_clean)
        results = [TestResultItem(**r) for r in data["results"]]
        overall = float(data.get("overall_score", 0))
        summary = data.get("summary", "")
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to parse LLM scoring response")

    return TestScoreResponse(results=results, overall_score=overall, summary=summary)
