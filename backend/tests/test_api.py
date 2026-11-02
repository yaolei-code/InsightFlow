from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db

def test_api_crud(db):
    app.dependency_overrides[get_db]=lambda:db
    try:
        client=TestClient(app)
        assert client.get('/api/health').json()['status']=='ok'
        r=client.post('/api/products',json={'name':'API Product','official_url':'https://example.org'})
        assert r.status_code==201
        pid=r.json()['id']
        assert client.patch(f'/api/products/{pid}',json={'name':'Renamed'}).json()['name']=='Renamed'
        assert client.post('/api/sources',json={'product_id':pid,'url':'http://127.0.0.1'}).status_code==400
        assert client.get('/api/products/9999').status_code==404
        assert client.get('/api/products?limit=1000').status_code==422
        assert client.get('/api/comparisons').json()['dimensions']
        assert client.post('/api/reports',json={'title':'Report'}).status_code==201
        assert client.delete(f'/api/products/{pid}').status_code==200
        assert client.get('/openapi.json').status_code==200
    finally: app.dependency_overrides.clear()

def test_comparison_distinguishes_unanalyzed_snapshot(db):
    from app.research import create_snapshot
    from app.models import Source
    source=db.get(Source,1)
    create_snapshot(db,source,'Training is publicly documented.',source.url)
    app.dependency_overrides[get_db]=lambda:db
    try:
        result=TestClient(app).get('/api/comparisons').json()
        assert result['claims']==[] and result['extraction_pending_products']==[1]
    finally:app.dependency_overrides.clear()
