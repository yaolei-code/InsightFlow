"""Local follows, reversible event grouping, quality and research audit."""
from alembic import op
import sqlalchemy as s
revision='006'
down_revision='005'
def upgrade():
    def record(name,*cols):op.create_table(name,s.Column('id',s.Integer,primary_key=True),s.Column('created_at',s.String,nullable=False),*cols)
    record('user_follows',s.Column('user_id',s.String,nullable=False),s.Column('target_type',s.String,nullable=False),s.Column('target_key',s.String,nullable=False),s.UniqueConstraint('user_id','target_type','target_key'))
    record('event_clusters',s.Column('fingerprint',s.String,nullable=False,unique=True),s.Column('method',s.String,nullable=False),s.Column('reason',s.String,nullable=False))
    op.create_table('cluster_members',s.Column('event_id',s.Integer,s.ForeignKey('progress_events.id'),primary_key=True),s.Column('cluster_id',s.Integer,s.ForeignKey('event_clusters.id'),nullable=False,index=True))
    op.create_table('event_assessments',s.Column('event_id',s.Integer,s.ForeignKey('progress_events.id'),primary_key=True),s.Column('score',s.Integer,nullable=False),s.Column('factors',s.JSON,nullable=False),s.Column('review_status',s.String,nullable=False),s.Column('reviewed_at',s.String),s.Column('updated_at',s.String,nullable=False))
    record('research_sessions',s.Column('user_query',s.Text,nullable=False),s.Column('parameters',s.JSON,nullable=False),s.Column('status',s.String,nullable=False,index=True),s.Column('trace',s.JSON,nullable=False),s.Column('summary',s.Text,nullable=False),s.Column('report_id',s.Integer,s.ForeignKey('research_reports.id')),s.Column('usage',s.JSON,nullable=False),s.Column('stop_reason',s.String),s.Column('finished_at',s.String))
def downgrade():
    for name in ('research_sessions','event_assessments','cluster_members','event_clusters','user_follows'):op.drop_table(name)
