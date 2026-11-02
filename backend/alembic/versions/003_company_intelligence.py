"""Add company intelligence without deleting product research history."""
from alembic import op
import sqlalchemy as sa
revision='003'
down_revision='002'

def upgrade():
    op.create_table('companies',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('name',sa.String,nullable=False,unique=True),sa.Column('category',sa.String,nullable=False),sa.Column('description',sa.Text,nullable=False),sa.Column('official_url',sa.String,nullable=False),sa.Column('technology_tags',sa.JSON,nullable=False),sa.Column('is_active',sa.Boolean,nullable=False),sa.Column('updated_at',sa.String,nullable=False))
    op.create_table('projects',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False,index=True),sa.Column('name',sa.String,nullable=False),sa.Column('technology_tags',sa.JSON,nullable=False),sa.Column('description',sa.Text,nullable=False),sa.UniqueConstraint('company_id','name'))
    with op.batch_alter_table('products') as batch:
        batch.add_column(sa.Column('company_id',sa.Integer,nullable=True))
        batch.create_foreign_key('fk_product_company','companies',['company_id'],['id'])
        batch.create_index('ix_products_company_id',['company_id'])
    with op.batch_alter_table('sources') as batch:
        batch.alter_column('product_id',existing_type=sa.Integer,nullable=True)
        batch.add_column(sa.Column('company_id',sa.Integer,nullable=True))
        batch.add_column(sa.Column('project_id',sa.Integer,nullable=True))
        batch.add_column(sa.Column('evidence_authority',sa.String,nullable=False,server_default='company_claim'))
        batch.create_foreign_key('fk_source_company','companies',['company_id'],['id'])
        batch.create_foreign_key('fk_source_project','projects',['project_id'],['id'])
        batch.create_index('ix_sources_company_id',['company_id'])
    op.add_column('research_tasks',sa.Column('task_kind',sa.String,nullable=False,server_default='product'))
    op.create_table('event_evidence',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False,index=True),sa.Column('snapshot_id',sa.Integer,sa.ForeignKey('snapshots.id'),nullable=False,index=True),sa.Column('source_url',sa.String,nullable=False),sa.Column('evidence_text',sa.Text,nullable=False),sa.Column('evidence_level',sa.String,nullable=False))
    op.create_table('progress_events',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False,index=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id')),sa.Column('snapshot_id',sa.Integer,sa.ForeignKey('snapshots.id'),nullable=False,index=True),*[sa.Column(n,sa.String,nullable=False) for n in ('event_type','title','description','progress_stage','evidence_level','verification_status')],sa.Column('published_at',sa.String,index=True),sa.Column('occurred_at',sa.String),*[sa.Column(n,sa.JSON,nullable=False) for n in ('capability_tags','evidence_ids','metrics')],sa.UniqueConstraint('snapshot_id','title'))
    op.create_table('progress_runs',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('snapshot_id',sa.Integer,sa.ForeignKey('snapshots.id'),nullable=False,unique=True),sa.Column('status',sa.String,nullable=False),sa.Column('error',sa.String),sa.Column('usage',sa.JSON,nullable=False),sa.Column('finished_at',sa.String))

def downgrade():
    raise RuntimeError('Company 迁移含研究历史，请先导出数据再人工回退，避免丢失事件。')
