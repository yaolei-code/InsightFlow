from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, utcnow


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Product(Record, Base):
    __tablename__ = "products"
    name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(default="")
    category: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(Text, default="")
    official_url: Mapped[str] = mapped_column(default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[str] = mapped_column(default=utcnow, onupdate=utcnow)


class Source(Record, Base):
    __tablename__ = "sources"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    url: Mapped[str]
    source_type: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    last_fetched_at: Mapped[str | None]
    last_status: Mapped[str] = mapped_column(default="pending")
    error: Mapped[str | None]


class Snapshot(Record, Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("source_id", "sequence"),)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    sequence: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str]


class Claim(Record, Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("snapshot_id", "dimension", "claim_text"),)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    dimension: Mapped[str]
    claim_text: Mapped[str] = mapped_column(Text)
    claim_status: Mapped[str]
    availability: Mapped[str]
    evidence_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str]
    observed_at: Mapped[str] = mapped_column(default=utcnow)
    verification_status: Mapped[str]


class ChangeEvent(Record, Base):
    __tablename__ = "change_events"
    __table_args__ = (UniqueConstraint("old_snapshot_id", "new_snapshot_id"),)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    old_snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    new_snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    change_type: Mapped[str]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    old_evidence: Mapped[str] = mapped_column(Text)
    new_evidence: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str]
    importance: Mapped[str]
    verification_status: Mapped[str]


class ImpactAnalysis(Record, Base):
    __tablename__ = "impact_analyses"
    target_product: Mapped[int] = mapped_column(ForeignKey("products.id"))
    competitor_product: Mapped[int] = mapped_column(ForeignKey("products.id"))
    change_event_id: Mapped[int] = mapped_column(ForeignKey("change_events.id"))
    data: Mapped[dict] = mapped_column(JSON)


class ResearchReport(Record, Base):
    __tablename__ = "research_reports"
    title: Mapped[str]
    markdown: Mapped[str] = mapped_column(Text)
    evidence_claim_ids: Mapped[list] = mapped_column(JSON)


class ResearchTask(Record, Base):
    __tablename__ = "research_tasks"
    status: Mapped[str] = mapped_column(default="queued", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    source_ids: Mapped[list] = mapped_column(JSON)
    finished_at: Mapped[str | None]
    usage: Mapped[dict] = mapped_column(JSON, default=dict)


class Comparison(Record, Base):
    __tablename__ = "comparisons"
    product_ids: Mapped[list] = mapped_column(JSON)
    relationship: Mapped[str]
    rationale: Mapped[str] = mapped_column(Text)
