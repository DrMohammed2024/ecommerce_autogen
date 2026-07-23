import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import ReflectedForeignKeyConstraint

from app.database.init_db import dispose_database, init_database
from app.database.session import engine


def _get_table_names(connection: Connection) -> set[str]:
    """Return all table names currently registered in the database."""

    inspector = inspect(connection)
    return set(inspector.get_table_names())


def _get_foreign_keys(
    connection: Connection,
    table_name: str,
) -> list[ReflectedForeignKeyConstraint]:
    """Return the foreign-key definitions for one database table."""

    inspector = inspect(connection)
    return inspector.get_foreign_keys(table_name)


@pytest.mark.asyncio
async def test_commerce_tables_are_created() -> None:
    """Verify that initialization creates all commerce tables."""

    await init_database()

    async with engine.connect() as connection:
        table_names = await connection.run_sync(_get_table_names)

    expected_tables = {
        "customers",
        "products",
        "orders",
        "order_items",
        "payments",
    }

    assert expected_tables.issubset(table_names)

    await dispose_database()


@pytest.mark.asyncio
async def test_commerce_foreign_keys_are_created() -> None:
    """Verify that commerce tables contain the required relationships."""

    await init_database()

    async with engine.connect() as connection:
        order_foreign_keys = await connection.run_sync(
            _get_foreign_keys,
            "orders",
        )
        order_item_foreign_keys = await connection.run_sync(
            _get_foreign_keys,
            "order_items",
        )
        payment_foreign_keys = await connection.run_sync(
            _get_foreign_keys,
            "payments",
        )

    order_targets = {
        foreign_key["referred_table"]
        for foreign_key in order_foreign_keys
    }
    order_item_targets = {
        foreign_key["referred_table"]
        for foreign_key in order_item_foreign_keys
    }
    payment_targets = {
        foreign_key["referred_table"]
        for foreign_key in payment_foreign_keys
    }

    assert "customers" in order_targets
    assert {"orders", "products"}.issubset(order_item_targets)
    assert "orders" in payment_targets

    await dispose_database()

