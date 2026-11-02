import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Product, Source

@pytest.fixture
def db(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'test.db'))
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as session:
        p=Product(name='Fixture product');session.add(p);session.flush()
        session.add(Source(product_id=p.id,url='https://example.com/',source_type='official_website'));session.commit()
        yield session
    engine.dispose()
