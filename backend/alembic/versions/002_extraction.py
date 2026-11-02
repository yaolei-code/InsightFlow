"""Saved-snapshot research tasks and durable extraction state."""
from alembic import op
import sqlalchemy as sa
revision='002'
down_revision='001'

def upgrade():
    op.add_column('research_tasks',sa.Column('snapshot_ids',sa.JSON(),nullable=False,server_default='[]'))
    op.create_table('extraction_runs',sa.Column('id',sa.Integer,primary_key=True),sa.Column('created_at',sa.String,nullable=False),sa.Column('snapshot_id',sa.Integer,sa.ForeignKey('snapshots.id'),nullable=False,unique=True),sa.Column('status',sa.String,nullable=False),sa.Column('error',sa.String),sa.Column('counts',sa.JSON,nullable=False),sa.Column('usage',sa.JSON,nullable=False),sa.Column('finished_at',sa.String))

def downgrade():
    op.drop_table('extraction_runs')
    with op.batch_alter_table('research_tasks') as batch:
        batch.drop_column('snapshot_ids')
