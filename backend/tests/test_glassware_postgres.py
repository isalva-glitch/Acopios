"""Opt-in real PostgreSQL tests. Every test creates and drops its own disposable database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
from uuid import uuid4
import pytest
from fastapi import HTTPException
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from config import settings
from models import Acopio
from models.glassware_import import GlasswareImport
from integrations.glassware.parser import parse_budget
from routers.glassware import confirm, Confirmation

pytestmark = pytest.mark.skipif(os.getenv('GLASSWARE_POSTGRES_TESTS') != '1', reason='Opt-in disposable PostgreSQL database')
FIXTURE = Path(__file__).parent / 'fixtures/glassware/parcial.json'


@pytest.fixture
def isolated_pg():
    admin_url = make_url(settings.database_url).set(drivername='postgresql', database='postgres')
    database_name = 'acopios_glassware_test_' + uuid4().hex
    assert database_name.startswith('acopios_glassware_test_') and len(database_name) < 64
    test_url = make_url(settings.database_url).set(database=database_name)
    engine = None
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
    try:
        env = dict(os.environ, DATABASE_URL=test_url.render_as_string(hide_password=False))
        result = subprocess.run(['alembic', 'upgrade', 'head'], env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        engine = create_engine(test_url)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        yield session_factory
    finally:
        if engine is not None:
            engine.dispose()
        # Drop only the exact random test database created above, never the application database.
        assert database_name.startswith('acopios_glassware_test_') and database_name != make_url(settings.database_url).database
        with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database_name)))


def seed(factory, count):
    data = parse_budget(json.loads(FIXTURE.read_text())).model_dump(mode='json')
    tokens = [str(uuid4()) for _ in range(count)]
    with factory.begin() as db:
        for token in tokens:
            db.add(GlasswareImport(token=token, glassware_id=data['metadata']['glassware_id'],
                numero=data['numero'], datos=data))
    return tokens


@pytest.mark.parametrize('same_preview', [True, False])
def test_concurrent_confirmations_create_exactly_one_acopio(isolated_pg, same_preview):
    factory = isolated_pg
    tokens = seed(factory, 1 if same_preview else 2)
    if same_preview: tokens *= 2
    barrier = threading.Barrier(2)
    def worker(token):
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                return 200, confirm(Confirmation(preview_id=token, aprobacion_verificada=True), db)
            except HTTPException as exc:
                return exc.status_code, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, tokens))
    if same_preview:
        assert [r[0] for r in results] == [200, 200]
        assert results[0][1]['acopio_id'] == results[1][1]['acopio_id']
        assert sorted(r[1]['already_created'] for r in results) == [False, True]
    else:
        assert sorted(r[0] for r in results) == [200, 409]
    with factory() as db:
        assert db.query(Acopio).count() == 1
        acopio = db.query(Acopio).one()
        assert acopio.total_unidades == acopio.saldo_unidades == 46
        assert sum(i.total_pesos for i in acopio.items) == acopio.total_pesos
        assert sum(a.cantidad for i in acopio.items for a in i.adicionales) == 144
        assert sum(p.cantidad for i in acopio.items for p in i.panos) == 46
        assert db.query(GlasswareImport).filter(GlasswareImport.acopio_id.isnot(None)).count() == 1
        assert db.query(GlasswareImport).filter(GlasswareImport.acopio_id.isnot(None)).one().datos['metadata']['aprobacion_verificada']



def test_postgres_delete_keeps_audit_and_does_not_resurrect_preview(isolated_pg):
    factory = isolated_pg
    token = seed(factory, 1)[0]
    with factory() as db:
        result = confirm(Confirmation(preview_id=token, aprobacion_verificada=True), db)
        aid = result['acopio_id']
        db.delete(db.get(Acopio, aid))
        db.commit()
    with factory() as db:
        row = db.query(GlasswareImport).one()
        assert row.acopio_id is None and row.confirmado_en is not None
        assert row.datos['metadata']['estado'] == 'Parcial'
        with pytest.raises(HTTPException) as exc:
            confirm(Confirmation(preview_id=token, aprobacion_verificada=True), db)
        assert exc.value.status_code == 409
        assert db.query(Acopio).count() == 0
