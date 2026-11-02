"""Optional manual review, automatic body-based ingestion audit."""
from alembic import op
import sqlalchemy as sa
revision='005'
down_revision='004'
def upgrade():
    op.add_column('source_candidates',sa.Column('decision_method',sa.String,nullable=False,server_default='unreviewed'))
    op.add_column('source_candidates',sa.Column('processing_status',sa.String,nullable=False,server_default='not_started'))
    op.add_column('source_candidates',sa.Column('processing_error',sa.String,nullable=True))
    op.create_index('ix_source_candidates_processing_status','source_candidates',['processing_status'])
def downgrade():
    with op.batch_alter_table('source_candidates') as batch:
        batch.drop_index('ix_source_candidates_processing_status')
        for key in ('decision_method','processing_status','processing_error'):batch.drop_column(key)
