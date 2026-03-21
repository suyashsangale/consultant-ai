import json
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.llm import call_llm
from app.database import get_db, AsyncSessionLocal
from app.models import User, KnowledgeBase, Conversation, Message
from app.schemas import ChatRequest, ChatResponse, ChatSources, ConversationOut, MessageOut
from app.auth import get_current_user
from app.knowledge import build_system_prompt, deep_merge, detect_hat
from app.embeddings import embed_sync
from app.vector_store import search_chunks
from app.config import get_settings

settings = get_settings()
router   = APIRouter(prefix="/chat", tags=["chat"])


def _parse_claude_response(raw: str) -> dict:
    text = raw.strip()

    # Strip any markdown code fence variant (```json, ```JSON, ```json5, ``` etc.)
    text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    # Attempt 1: direct parse (fast path — works when JSON mode is active)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: scan for the first valid JSON object using the stdlib decoder.
    # raw_decode(text, pos) parses starting at pos and stops at the matching brace,
    # so it handles prose before/after the JSON block without manual brace counting.
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text, i)
                return obj
            except json.JSONDecodeError:
                continue

    # Fallback: treat entire response as plain reply text
    return {
        "reply": raw,
        "knowledge_updates": {},
        "phase": "discovery",
        "knowledge_gaps": [],
        "detected_hat": "auto",
    }


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    biz_id = current_user.business_id

    # ── Load or create conversation ───────────────────────────────────────
    if body.conversation_id:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.business_id == biz_id,
            )
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(business_id=biz_id)
        db.add(conversation)
        await db.flush()

    # ── Load knowledge base ───────────────────────────────────────────────
    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == biz_id)
    )
    kb_record = kb_result.scalar_one_or_none()
    if not kb_record:
        kb_record = KnowledgeBase(business_id=biz_id, data={}, phase="discovery", gaps=[])
        db.add(kb_record)
        await db.flush()

    # ── Load conversation history (last 40 messages) ──────────────────────
    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.order)
    )
    history = msgs_result.scalars().all()

    is_greeting = not history and not body.message.strip()
    claude_messages = [{"role": m.role, "content": m.content} for m in history[-40:]]

    if is_greeting:
        claude_messages = [{"role": "user", "content": "Hello, introduce yourself and start our session."}]
        save_user_msg = False
    else:
        save_user_msg = True
        claude_messages.append({"role": "user", "content": body.message})

    # ── Detect hat ────────────────────────────────────────────────────────
    hat = detect_hat(body.message)

    # ── RAG: embed query and retrieve relevant document chunks ────────────
    doc_context = []
    if body.message.strip() and kb_record.phase == "consulting":
        try:
            query_embedding = embed_sync([body.message])[0]
            async with AsyncSessionLocal() as rag_db:
                doc_context = await search_chunks(rag_db, biz_id, query_embedding, limit=4)
        except Exception:
            doc_context = []  # RAG is best-effort; never block the chat

    # ── Build system prompt ───────────────────────────────────────────────
    from app.models import Business
    biz_result = await db.execute(select(Business).where(Business.id == biz_id))
    business   = biz_result.scalar_one()

    system_prompt = build_system_prompt(
        kb=kb_record.data,
        business_name=business.name,
        hat=hat,
        doc_context=doc_context if doc_context else None,
    )

    # ── Call LLM ──────────────────────────────────────────────────────────
    try:
        raw_reply = call_llm(
            system=system_prompt,
            messages=claude_messages,
            max_tokens=1500,
            json_mode=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")

    # ── Parse response ────────────────────────────────────────────────────
    parsed            = _parse_claude_response(raw_reply)
    reply_text        = parsed.get("reply", raw_reply)
    knowledge_updates = parsed.get("knowledge_updates", {})
    new_phase         = parsed.get("phase", kb_record.phase)
    gaps              = parsed.get("knowledge_gaps", [])

    # ── Persist KB updates ────────────────────────────────────────────────
    if knowledge_updates:
        kb_record.data = deep_merge(kb_record.data, knowledge_updates)
    kb_record.phase = new_phase
    kb_record.gaps  = gaps[:4]

    # ── Persist messages ──────────────────────────────────────────────────
    next_order = len(history)
    if save_user_msg and body.message:
        db.add(Message(
            conversation_id=conversation.id,
            role="user",
            content=body.message,
            order=next_order,
        ))
        next_order += 1

    db.add(Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_text,
        knowledge_updates=knowledge_updates,
        order=next_order,
    ))

    if not history and conversation.title == "New conversation":
        conversation.title = (body.message or "Getting started")[:60]

    # Touch updated_at so list_conversations sorts by latest activity
    from datetime import datetime, timezone
    conversation.updated_at = datetime.now(timezone.utc)

    await db.commit()

    sources = ChatSources(
        kb_categories=[c for c in kb_record.data if kb_record.data.get(c)],
        doc_chunks=len(doc_context),
    )

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply_text,
        knowledge_updates=knowledge_updates,
        phase=new_phase,
        knowledge_gaps=gaps[:4],
        sources=sources,
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.business_id == current_user.business_id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.business_id == current_user.business_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.order)
    )
    messages = msgs_result.scalars().all()
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )
