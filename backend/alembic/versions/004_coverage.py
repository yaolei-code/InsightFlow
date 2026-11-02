"""Discovery library and review boundary; saved snapshots remain evidence."""
from alembic import op
import sqlalchemy as sa
revision='004'
down_revision='003'

def upgrade():
    for name in ('title','published_at','source_type'):
        op.add_column('snapshots',sa.Column(name,sa.String,nullable=True))
    op.add_column('snapshots',sa.Column('capture_status',sa.String,nullable=False,server_default='success'))
    def table(name,*cols):
        op.create_table(name,sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),*cols)
    def text(name,nullable=False):return sa.Column(name,sa.String,nullable=nullable)
    def company():return sa.Column('company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=True,index=True)
    table('discovery_seeds',text('name'),sa.Column('url',sa.String,nullable=False,unique=True),text('source_type'),company(),sa.Column('is_active',sa.Boolean,nullable=False),text('last_status'),text('last_checked_at',True),text('error',True))
    table('company_aliases',company(),sa.Column('alias',sa.String,nullable=False,unique=True))
    table('source_candidates',text('title'),sa.Column('url',sa.String,nullable=False,unique=True),sa.Column('domain',sa.String,nullable=False,index=True),text('source_type'),company(),text('discovered_by'),text('discovery_query'),text('published_at',True),text('discovered_at'),sa.Column('snippet',sa.Text,nullable=False),sa.Column('relevance_score',sa.Integer,nullable=False),text('source_trust_level'),sa.Column('review_status',sa.String,nullable=False,index=True),sa.Column('source_id',sa.Integer,sa.ForeignKey('sources.id')),sa.Column('discovery_history',sa.JSON,nullable=False))
    table('discovery_runs',text('status'),text('kind'),sa.Column('parameters',sa.JSON,nullable=False),sa.Column('result',sa.JSON,nullable=False),text('error',True),text('finished_at',True))

def downgrade():
    for name in ('discovery_runs','source_candidates','company_aliases','discovery_seeds'):op.drop_table(name)
    with op.batch_alter_table('snapshots') as batch:
        for name in ('title','published_at','source_type','capture_status'):batch.drop_column(name)
