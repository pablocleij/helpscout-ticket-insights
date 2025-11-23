"""Database models for tickets, conversations, and analyses."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    Index,
    Float,
)
from sqlalchemy.orm import relationship

from src.database import Base


class Ticket(Base):
    """HelpScout conversation/ticket."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    helpscout_id = Column(Integer, unique=True, nullable=False, index=True)
    number = Column(Integer, nullable=False)
    subject = Column(String(500))
    status = Column(String(50), index=True)
    type = Column(String(50))
    mailbox_id = Column(Integer, index=True)
    mailbox_name = Column(String(200))
    customer_email = Column(String(255), index=True)
    customer_name = Column(String(255))
    created_at = Column(DateTime, nullable=False, index=True)
    updated_at = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True)
    tags = Column(JSON)  # List of tag strings
    custom_fields = Column(JSON)  # Dict of custom fields
    raw_data = Column(JSON)  # Full API response

    # Relationships
    threads = relationship("Thread", back_populates="ticket", cascade="all, delete-orphan")
    analysis = relationship(
        "TicketAnalysis", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_tickets_created_at_status", "created_at", "status"),
        Index("idx_tickets_mailbox_created", "mailbox_id", "created_at"),
    )


class Thread(Base):
    """Individual message thread in a conversation."""

    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    helpscout_id = Column(Integer, unique=True, nullable=False, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50))  # message, customer, note, etc.
    body = Column(Text)
    body_plain = Column(Text)  # Stripped HTML
    created_by_email = Column(String(255))
    created_by_name = Column(String(255))
    created_at = Column(DateTime, nullable=False, index=True)
    is_customer = Column(Boolean, default=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="threads")


class TicketAnalysis(Base):
    """LLM analysis results for a ticket."""

    __tablename__ = "ticket_analyses"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    # Analysis results
    category = Column(String(100), index=True)  # Primary category
    subcategory = Column(String(100), index=True)  # Subcategory
    pain_points = Column(JSON)  # List of identified pain points
    topics = Column(JSON)  # List of topics/categories
    sentiment = Column(String(50))  # positive, negative, neutral
    urgency_score = Column(Float)  # 0-1 scale
    suggested_tags = Column(JSON)  # List of suggested tags
    summary = Column(Text)  # Brief summary of the issue

    # Metadata
    analyzed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    llm_provider = Column(String(50))
    llm_model = Column(String(100))
    raw_response = Column(JSON)  # Full LLM response

    # Relationships
    ticket = relationship("Ticket", back_populates="analysis")

    __table_args__ = (
        Index("idx_analysis_analyzed_at", "analyzed_at"),
        Index("idx_analysis_category", "category", "subcategory"),
    )


class AggregatedInsight(Base):
    """Aggregated insights across tickets for a time period."""

    __tablename__ = "aggregated_insights"

    id = Column(Integer, primary_key=True, index=True)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    mailbox_id = Column(Integer, nullable=True, index=True)

    # Aggregated data
    top_pain_points = Column(JSON)  # [{pain_point: str, count: int, tickets: [ids]}]
    top_topics = Column(JSON)  # [{topic: str, count: int}]
    sentiment_distribution = Column(JSON)  # {positive: int, negative: int, neutral: int}
    average_urgency = Column(Float)
    total_tickets_analyzed = Column(Integer)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_insights_period", "period_start", "period_end"),
        Index("idx_insights_mailbox_period", "mailbox_id", "period_start", "period_end"),
    )


class SyncState(Base):
    """Track sync state for incremental updates."""

    __tablename__ = "sync_states"

    id = Column(Integer, primary_key=True, index=True)
    mailbox_id = Column(Integer, unique=True, nullable=False, index=True)
    last_sync_at = Column(DateTime, nullable=False)
    last_ticket_id = Column(Integer, nullable=True)
    last_modified_at = Column(DateTime, nullable=True)
    total_tickets_synced = Column(Integer, default=0)
    sync_cursor = Column(String(255), nullable=True)  # For cursor-based pagination

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
