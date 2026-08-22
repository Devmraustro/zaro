"""Migration tests: 0004 must apply cleanly and roll back on SQLite.

These run alembic against a throwaway file database, proving the migration
chain is executable end-to-end (not just metadata-identical to the models).
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def sqlite_url():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield f"sqlite:///{path}"
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def alembic_env(sqlite_url, monkeypatch):
    # env.py resolves the URL through get_settings() (lru_cached), so the
    # env var must be in place before the cache is (re)populated.
    # Alembic runs migrations through an async engine -> needs aiosqlite;
    # verification in the tests uses the plain sync sqlite_url instead.
    async_url = sqlite_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    monkeypatch.setenv("ZARO_DATABASE_URL", async_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield async_url
    get_settings.cache_clear()


def _alembic_config():
    from alembic.config import Config

    return Config("alembic.ini")


def _upgrade(target: str) -> None:
    from alembic import command

    command.upgrade(_alembic_config(), target)


def _downgrade(target: str) -> None:
    # command.upgrade() refuses to move below the current revision;
    # downward moves must go through command.downgrade().
    from alembic import command

    command.downgrade(_alembic_config(), target)


def test_upgrade_head_creates_commerce_tables(alembic_env, sqlite_url):
    _upgrade("head")

    engine = create_engine(sqlite_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected = {
            "categories",
            "products",
            "product_variants",
            "materials",
            "material_prices",
            "customers",
            "custom_requests",
            "file_assets",
        }
        missing = expected - tables
        assert not missing, f"Missing tables after upgrade: {missing}"

        # Spot-check critical columns.
        product_cols = {c["name"] for c in inspector.get_columns("products")}
        assert {"product_code", "slug", "selling_price_minor", "currency", "status"} <= product_cols
        price_cols = {c["name"] for c in inspector.get_columns("material_prices")}
        assert {"material_id", "effective_from", "unit_price_minor"} <= price_cols
        asset_cols = {c["name"] for c in inspector.get_columns("file_assets")}
        assert {"storage_key", "sha256", "purpose", "visibility"} <= asset_cols
    finally:
        engine.dispose()


def test_downgrade_removes_phase2_tables(alembic_env, sqlite_url):
    _upgrade("head")
    _downgrade("0003")

    engine = create_engine(sqlite_url)
    try:
        tables = set(inspect(engine).get_table_names())
        for table in ("products", "categories", "materials", "customers", "custom_requests", "file_assets"):
            assert table not in tables, f"{table} should have been dropped by downgrade"
        # Phase 1 tables remain.
        assert "users" in tables
    finally:
        engine.dispose()


def test_migration_chain_is_reversible(alembic_env, sqlite_url):
    """Full up-down-up cycle proves idempotent chain integrity."""
    _upgrade("head")
    _downgrade("base")
    _upgrade("head")

    engine = create_engine(sqlite_url)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0004"
    finally:
        engine.dispose()
