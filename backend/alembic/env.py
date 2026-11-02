from alembic import context
from app.db import Base, engine
from app import models

if context.is_offline_mode():
    context.configure(url=str(engine.url),target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        if connection.dialect.name=='sqlite':
            # Batch rebuilds reference existing tables. Verify all FKs before re-enabling.
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            connection.commit()
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        if connection.dialect.name=='sqlite':
            violations=connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
            if violations:raise RuntimeError('迁移后外键检查失败')
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
