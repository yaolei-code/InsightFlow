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
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), index=True)
    category: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(Text, default="")
    official_url: Mapped[str] = mapped_column(default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[str] = mapped_column(default=utcnow, onupdate=utcnow)


class Source(Record, Base):
    __tablename__ = "sources"
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id'))
    evidence_authority: Mapped[str] = mapped_column(default='company_claim')
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
    title: Mapped[str | None]
    published_at: Mapped[str | None]
    source_type: Mapped[str | None]
    capture_status: Mapped[str] = mapped_column(default='success')


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
    snapshot_ids: Mapped[list] = mapped_column(JSON, default=list)
    task_kind: Mapped[str] = mapped_column(default='product')
    finished_at: Mapped[str | None]
    usage: Mapped[dict] = mapped_column(JSON, default=dict)


class ExtractionRun(Record, Base):
    __tablename__ = 'extraction_runs'
    snapshot_id: Mapped[int] = mapped_column(ForeignKey('snapshots.id'), unique=True)
    status: Mapped[str]
    error: Mapped[str | None]
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    finished_at: Mapped[str | None]


class Comparison(Record, Base):
    __tablename__ = "comparisons"
    product_ids: Mapped[list] = mapped_column(JSON)
    relationship: Mapped[str]
    rationale: Mapped[str] = mapped_column(Text)


class Company(Record, Base):
    __tablename__='companies'
    name: Mapped[str] = mapped_column(unique=True)
    category: Mapped[str] = mapped_column(default='待研究')
    description: Mapped[str] = mapped_column(Text,default='')
    official_url: Mapped[str] = mapped_column(default='')
    technology_tags: Mapped[list] = mapped_column(JSON,default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[str] = mapped_column(default=utcnow,onupdate=utcnow)


class Project(Record, Base):
    __tablename__='projects'
    __table_args__=(UniqueConstraint('company_id','name'),)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'),index=True)
    name: Mapped[str]
    technology_tags: Mapped[list] = mapped_column(JSON,default=list)
    description: Mapped[str] = mapped_column(Text,default='')


class EventEvidence(Record, Base):
    __tablename__='event_evidence'
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'),index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey('snapshots.id'),index=True)
    source_url: Mapped[str]
    evidence_text: Mapped[str] = mapped_column(Text)
    evidence_level: Mapped[str]


class ProgressEvent(Record, Base):
    __tablename__='progress_events'
    __table_args__=(UniqueConstraint('snapshot_id','title'),)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'),index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id'))
    snapshot_id: Mapped[int] = mapped_column(ForeignKey('snapshots.id'),index=True)
    event_type: Mapped[str]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    capability_tags: Mapped[list] = mapped_column(JSON)
    progress_stage: Mapped[str]
    published_at: Mapped[str | None] = mapped_column(index=True)
    occurred_at: Mapped[str | None]
    evidence_ids: Mapped[list] = mapped_column(JSON)
    evidence_level: Mapped[str]
    verification_status: Mapped[str]
    metrics: Mapped[list] = mapped_column(JSON)


class ProgressRun(Record, Base):
    __tablename__='progress_runs'
    snapshot_id: Mapped[int] = mapped_column(ForeignKey('snapshots.id'),unique=True)
    status: Mapped[str]
    error: Mapped[str | None]
    usage: Mapped[dict] = mapped_column(JSON,default=dict)
    finished_at: Mapped[str | None]


class DiscoverySeed(Record,Base):
    __tablename__='discovery_seeds'
    name: Mapped[str]
    url: Mapped[str] = mapped_column(unique=True)
    source_type: Mapped[str]
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'))
    is_active: Mapped[bool] = mapped_column(default=True)
    last_status: Mapped[str] = mapped_column(default='pending')
    last_checked_at: Mapped[str | None]
    error: Mapped[str | None]


class CompanyAlias(Record,Base):
    __tablename__='company_aliases'
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'),index=True)
    alias: Mapped[str] = mapped_column(unique=True)


class SourceCandidate(Record,Base):
    __tablename__='source_candidates'
    title: Mapped[str]
    url: Mapped[str] = mapped_column(unique=True)
    domain: Mapped[str] = mapped_column(index=True)
    source_type: Mapped[str]
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'),index=True)
    discovered_by: Mapped[str]
    discovery_query: Mapped[str]
    published_at: Mapped[str | None]
    discovered_at: Mapped[str] = mapped_column(default=utcnow)
    snippet: Mapped[str] = mapped_column(Text,default='')
    relevance_score: Mapped[int]
    source_trust_level: Mapped[str]
    review_status: Mapped[str] = mapped_column(default='pending',index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey('sources.id'))
    discovery_history: Mapped[list] = mapped_column(JSON,default=list)


class DiscoveryRun(Record,Base):
    __tablename__='discovery_runs'
    status: Mapped[str] = mapped_column(default='queued')
    kind: Mapped[str]
    parameters: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON,default=dict)
    error: Mapped[str | None]
    finished_at: Mapped[str | None]
