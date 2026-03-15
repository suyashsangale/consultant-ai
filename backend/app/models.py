import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, JSON,
    Boolean, Integer, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ── Business ──────────────────────────────────────────────────────────────────

class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]     = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100))
    size:     Mapped[str | None] = mapped_column(String(100))
    stage:    Mapped[str | None] = mapped_column(String(100))
    # Stripe customer ID — set on first checkout
    stripe_customer_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    users:         Mapped[list["User"]]              = relationship(back_populates="business")
    knowledge_base: Mapped["KnowledgeBase | None"]   = relationship(back_populates="business", uselist=False)
    conversations: Mapped[list["Conversation"]]      = relationship(back_populates="business")
    documents:     Mapped[list["Document"]]          = relationship(back_populates="business")
    subscription:  Mapped["Subscription | None"]     = relationship(back_populates="business", uselist=False)
    invites:       Mapped[list["Invite"]]            = relationship(back_populates="business")
    integrations:  Mapped[list["Integration"]]       = relationship(back_populates="business")


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:             Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email:          Mapped[str]       = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    full_name:      Mapped[str | None] = mapped_column(String(200))
    role:           Mapped[str]       = mapped_column(String(50), default="owner")  # owner | admin | member
    is_active:      Mapped[bool]      = mapped_column(Boolean, default=True)
    business_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    created_at:     Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped["Business"] = relationship(back_populates="users")


# ── Subscription ──────────────────────────────────────────────────────────────

class Subscription(Base):
    """One subscription per business. Synced from Stripe webhooks."""
    __tablename__ = "subscriptions"

    id:                  Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id:         Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    plan:                Mapped[str]           = mapped_column(String(50), default="free")   # free | pro | business
    status:              Mapped[str]           = mapped_column(String(50), default="active") # active | past_due | canceled | trialing
    current_period_end:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool]         = mapped_column(Boolean, default=False)
    updated_at:          Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    business: Mapped["Business"] = relationship(back_populates="subscription")


# ── Invite ────────────────────────────────────────────────────────────────────

class Invite(Base):
    """Pending team invitation. Expires after 7 days."""
    __tablename__ = "invites"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    email:       Mapped[str]       = mapped_column(String(320), nullable=False)
    role:        Mapped[str]       = mapped_column(String(50), default="member")   # admin | member
    token:       Mapped[str]       = mapped_column(String(64), unique=True, nullable=False)
    invited_by:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    accepted:    Mapped[bool]      = mapped_column(Boolean, default=False)
    expires_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True))
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped["Business"] = relationship(back_populates="invites")


# ── Integration ───────────────────────────────────────────────────────────────

class Integration(Base):
    """
    A connected external source: email (IMAP) or slack.
    Credentials are stored as JSON — encrypt at rest in production.
    """
    __tablename__ = "integrations"

    id:           Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id:  Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    type:         Mapped[str]          = mapped_column(String(50), nullable=False)   # email | slack
    name:         Mapped[str]          = mapped_column(String(200), nullable=False)  # display name
    config:       Mapped[dict]         = mapped_column(JSON, default=dict)           # credentials + settings
    status:       Mapped[str]          = mapped_column(String(50), default="active") # active | error | paused
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error:   Mapped[str | None]   = mapped_column(Text)
    created_at:   Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped["Business"] = relationship(back_populates="integrations")


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True)
    data:        Mapped[dict]      = mapped_column(JSON, default=dict)
    phase:       Mapped[str]       = mapped_column(String(50), default="discovery")
    gaps:        Mapped[list]      = mapped_column(JSON, default=list)
    updated_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    business: Mapped["Business"] = relationship(back_populates="knowledge_base")


# ── Conversation + Message ────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    title:       Mapped[str]       = mapped_column(String(300), default="New conversation")
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    business: Mapped["Business"]     = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id:                Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id:   Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    role:              Mapped[str]          = mapped_column(String(20))
    content:           Mapped[str]          = mapped_column(Text)
    knowledge_updates: Mapped[dict | None]  = mapped_column(JSON)
    created_at:        Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utcnow)
    order:             Mapped[int]          = mapped_column(Integer, default=0)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ── Document ──────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id:            Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id:   Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    filename:      Mapped[str]            = mapped_column(String(500), nullable=False)
    original_name: Mapped[str]            = mapped_column(String(500), nullable=False)
    file_type:     Mapped[str]            = mapped_column(String(20),  nullable=False)
    file_size:     Mapped[int]            = mapped_column(BigInteger, default=0)
    status:        Mapped[str]            = mapped_column(String(30), default="processing")
    chunk_count:   Mapped[int]            = mapped_column(Integer, default=0)
    source:        Mapped[str]            = mapped_column(String(50), default="upload")  # upload | email | slack
    error_message: Mapped[str | None]     = mapped_column(Text)
    created_at:    Mapped[datetime]       = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    business: Mapped["Business"] = relationship(back_populates="documents")
