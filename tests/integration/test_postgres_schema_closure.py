from __future__ import annotations

import os

import pytest

from scripts.verify_postgres_schema import run_verification


def test_postgresql_16_alembic_head_and_minimal_crud() -> None:
    database_url = os.getenv("ECOM_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Set ECOM_TEST_POSTGRES_URL to run the PostgreSQL 16 schema closure test.")

    run_verification(database_url=database_url, reset_schema=True, downgrade_check=True)
