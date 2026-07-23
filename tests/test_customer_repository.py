from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.database.commerce_models import CustomerRecord
from app.database.init_db import init_database
from app.database.session import AsyncSessionFactory
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository

_TEST_EMAIL_PATTERN = "repo-test-%@example.com"


@pytest.fixture(autouse=True)
async def isolate_customer_repository_records() -> AsyncIterator[None]:
    """Initialize the schema and isolate records created by this test module."""

    await init_database()

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(CustomerRecord).where(
                CustomerRecord.email.like(_TEST_EMAIL_PATTERN)
            )
        )
        await session.commit()

    yield

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(CustomerRecord).where(
                CustomerRecord.email.like(_TEST_EMAIL_PATTERN)
            )
        )
        await session.commit()


def _customer(
    email: str,
    *,
    full_name: str = "Repository Test Customer",
    phone: str | None = "+15550001000",
    is_active: bool = True,
) -> Customer:
    """Build one validated customer for repository tests."""

    return Customer(
        full_name=full_name,
        email=email,
        phone=phone,
        is_active=is_active,
    )


async def test_create_persists_customer() -> None:
    customer = _customer("repo-test-create@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        created = await repository.create(customer)

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        stored = await repository.get_by_id(customer.id)

    assert created == customer
    assert stored is not None
    assert stored.id == customer.id
    assert stored.email == customer.email


async def test_get_by_id_returns_customer() -> None:
    customer = _customer("repo-test-by-id@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(customer)
        stored = await repository.get_by_id(customer.id)

    assert stored is not None
    assert stored.id == customer.id
    assert stored.full_name == customer.full_name


async def test_get_by_email_returns_customer() -> None:
    customer = _customer("repo-test-by-email@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(customer)
        stored = await repository.get_by_email(customer.email)

    assert stored is not None
    assert stored.id == customer.id
    assert stored.email == customer.email


async def test_get_by_id_returns_none_for_unknown_customer() -> None:
    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        stored = await repository.get_by_id(uuid4())

    assert stored is None


async def test_get_by_email_returns_none_for_unknown_customer() -> None:
    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        stored = await repository.get_by_email(
            "repo-test-unknown@example.com"
        )

    assert stored is None


async def test_list_active_returns_only_active_customers() -> None:
    active_customer = _customer("repo-test-active@example.com")
    inactive_customer = _customer(
        "repo-test-inactive@example.com",
        is_active=False,
    )

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(active_customer)
        await repository.create(inactive_customer)
        active_customers = await repository.list_active(limit=500)

    active_ids = {customer.id for customer in active_customers}

    assert active_customer.id in active_ids
    assert inactive_customer.id not in active_ids


async def test_update_changes_only_mutable_customer_fields() -> None:
    original = _customer(
        "repo-test-update-original@example.com",
        full_name="Original Customer",
        phone="+15550002000",
    )
    replacement = Customer(
        id=uuid4(),
        full_name="Updated Customer",
        email="repo-test-update-new@example.com",
        phone="+15550003000",
        is_active=False,
    )

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(original)
        updated = await repository.update(original.id, replacement)

    assert updated is not None
    assert updated.id == original.id
    assert updated.created_at == original.created_at
    assert updated.full_name == "Updated Customer"
    assert str(updated.email) == "repo-test-update-new@example.com"
    assert updated.phone == "+15550003000"
    assert updated.is_active is False


async def test_update_returns_none_for_unknown_customer() -> None:
    replacement = _customer("repo-test-update-missing@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        updated = await repository.update(uuid4(), replacement)

    assert updated is None


async def test_deactivate_marks_customer_inactive() -> None:
    customer = _customer("repo-test-deactivate@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(customer)
        deactivated = await repository.deactivate(customer.id)

    assert deactivated is not None
    assert deactivated.id == customer.id
    assert deactivated.is_active is False


async def test_deactivate_is_idempotent() -> None:
    customer = _customer("repo-test-idempotent@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(customer)
        first_result = await repository.deactivate(customer.id)
        second_result = await repository.deactivate(customer.id)

    assert first_result is not None
    assert second_result is not None
    assert first_result.id == second_result.id
    assert first_result.is_active is False
    assert second_result.is_active is False


async def test_deactivated_customer_is_excluded_from_active_list() -> None:
    customer = _customer("repo-test-excluded@example.com")

    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)
        await repository.create(customer)
        await repository.deactivate(customer.id)
        active_customers = await repository.list_active(limit=500)

    active_ids = {active_customer.id for active_customer in active_customers}

    assert customer.id not in active_ids


async def test_list_active_rejects_non_positive_limit() -> None:
    async with AsyncSessionFactory() as session:
        repository = CustomerRepository(session)

        with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
        ):
            await repository.list_active(limit=0)
