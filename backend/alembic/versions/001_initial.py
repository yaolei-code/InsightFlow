"""Initial MVP schema. Metadata is frozen in this revision module."""
from alembic import op
from sqlalchemy import MetaData, Table, Column, Integer, Text, String, Boolean, JSON, ForeignKey, UniqueConstraint

revision='001'
down_revision=None

def schema():
    md=MetaData()
    def table(name,*cols):
        return Table(name,md,Column('id',Integer,primary_key=True),Column('created_at',String,nullable=False),*cols)
    def text(name): return Column(name,String,nullable=False)
    def fk(name,target): return Column(name,Integer,ForeignKey(target+'.id'),nullable=False,index=True)
    table('products',text('name'),text('company'),text('category'),Column('description',Text,nullable=False),text('official_url'),Column('is_active',Boolean,nullable=False),text('updated_at'))
    table('sources',fk('product_id','products'),text('url'),text('source_type'),Column('is_active',Boolean,nullable=False),Column('last_fetched_at',String),text('last_status'),Column('error',String))
    table('snapshots',fk('source_id','sources'),Column('sequence',Integer,nullable=False),Column('content',Text,nullable=False),Column('content_hash',String(64),nullable=False,index=True),text('source_url'),UniqueConstraint('source_id','sequence'))
    table('claims',fk('product_id','products'),fk('snapshot_id','snapshots'),text('dimension'),Column('claim_text',Text,nullable=False),text('claim_status'),text('availability'),Column('evidence_text',Text,nullable=False),text('source_url'),text('observed_at'),text('verification_status'),UniqueConstraint('snapshot_id','dimension','claim_text'))
    table('change_events',fk('product_id','products'),fk('old_snapshot_id','snapshots'),fk('new_snapshot_id','snapshots'),text('change_type'),text('title'),Column('description',Text,nullable=False),Column('old_evidence',Text,nullable=False),Column('new_evidence',Text,nullable=False),text('source_url'),text('importance'),text('verification_status'),UniqueConstraint('old_snapshot_id','new_snapshot_id'))
    table('impact_analyses',fk('target_product','products'),fk('competitor_product','products'),fk('change_event_id','change_events'),Column('data',JSON,nullable=False))
    table('research_reports',text('title'),Column('markdown',Text,nullable=False),Column('evidence_claim_ids',JSON,nullable=False))
    table('research_tasks',Column('status',String,nullable=False,index=True),Column('progress',Integer,nullable=False),Column('logs',JSON,nullable=False),Column('source_ids',JSON,nullable=False),Column('finished_at',String),Column('usage',JSON,nullable=False))
    table('comparisons',Column('product_ids',JSON,nullable=False),text('relationship'),Column('rationale',Text,nullable=False))
    return md

def upgrade(): schema().create_all(op.get_bind())
def downgrade(): schema().drop_all(op.get_bind())
