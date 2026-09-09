"""Guards for commerce fixes: retry helper, transition maps, search, prices."""

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, InvalidStateTransition
from app.models.enums import PaymentStatus, QuoteStatus
from app.services import payments_service
from app.services.references import is_unique_violation, run_with_unique_retry


def _unique_error() -> IntegrityError:
    return IntegrityError("INSERT INTO t", {}, sqlite3.IntegrityError("UNIQUE constraint failed: t.ref"))


def _check_error() -> IntegrityError:
    return IntegrityError("INSERT INTO t", {}, sqlite3.IntegrityError("CHECK constraint failed: t.ck"))


class TestRunWithUniqueRetry:
    async def test_success_first_try(self, db_session):
        calls = []

        async def attempt():
            calls.append(1)
            return "ok"

        assert await run_with_unique_retry(db_session, attempt) == "ok"
        assert len(calls) == 1

    async def test_retries_unique_violation_then_succeeds(self, db_session):
        calls = []

        async def attempt():
            calls.append(1)
            if len(calls) == 1:
                raise _unique_error()
            return "recovered"

        assert await run_with_unique_retry(db_session, attempt) == "recovered"
        assert len(calls) == 2

    async def test_persistent_conflict_becomes_409(self, db_session):
        async def attempt():
            raise _unique_error()

        with pytest.raises(ConflictError, match="already exists"):
            await run_with_unique_retry(db_session, attempt, conflict_message="already exists")

    async def test_non_unique_violation_propagates_unretried(self, db_session):
        calls = []

        async def attempt():
            calls.append(1)
            raise _check_error()

        with pytest.raises(IntegrityError):
            await run_with_unique_retry(db_session, attempt)
        assert len(calls) == 1

    def test_is_unique_violation_detection(self):
        assert is_unique_violation(_unique_error()) is True
        assert is_unique_violation(_check_error()) is False


class TestPaymentTransitions:
    def test_proof_can_be_replaced_before_submit(self):
        payments_service.validate_transition(PaymentStatus.PROOF_UPLOADED, PaymentStatus.PROOF_UPLOADED)

    def test_reject_after_confirm_rejected(self):
        with pytest.raises(InvalidStateTransition):
            payments_service.validate_transition(PaymentStatus.CONFIRMED, PaymentStatus.CANCELLED)

    def test_submit_after_confirm_rejected(self):
        with pytest.raises(InvalidStateTransition):
            payments_service.validate_transition(PaymentStatus.CONFIRMED, PaymentStatus.UNDER_REVIEW)


class TestDepositDoubleApply:
    async def test_second_deposit_application_rejected(self, db_session):
        """apply_confirmed_deposit requires PENDING_DEPOSIT (guard + lock)."""
        from app.models.customer import Customer
        from app.services import orders_service, quotes_service

        customer = Customer(full_name="Double Pay", email="double-pay@example.com")
        db_session.add(customer)
        await db_session.commit()
        quote = await quotes_service.create_quote(
            db_session,
            customer_id=customer.id,
            custom_request_id=None,
            lines=[
                quotes_service.QuoteLineInput.build(
                    description="Desk", quantity=1, unit_label="pcs", unit_price_minor=40000
                )
            ],
            valid_until=datetime.now(UTC) + timedelta(days=7),
        )
        quote = await quotes_service.change_status(db_session, quote, QuoteStatus.SENT)
        quote = await quotes_service.change_status(db_session, quote, QuoteStatus.ACCEPTED)
        order = await orders_service.create_from_quote(db_session, quote)
        order = await orders_service.apply_confirmed_deposit(
            db_session, order, amount_minor=order.deposit_required_minor
        )
        with pytest.raises(ConflictError):
            await orders_service.apply_confirmed_deposit(db_session, order, amount_minor=100)


class TestCustomerSearchEscaping:
    async def test_percent_in_search_is_literal(self, db_session):
        from app.services import customers_service

        await customers_service.create_customer(db_session, {"full_name": "100% Cotton Co", "email": "a@example.com"})
        await customers_service.create_customer(db_session, {"full_name": "100X Cotton Co", "email": "b@example.com"})
        items, total = await customers_service.list_customers(db_session, page=1, page_size=20, search="100%")
        assert total == 1
        assert items[0].full_name == "100% Cotton Co"


class TestAddPrice:
    async def test_duplicate_effective_date_conflicts_without_killing_session(self, db_session):
        """add_price uses a SAVEPOINT: a 409 must not discard the caller's txn."""
        from app.models.material import Material
        from app.services import materials_service

        material_id = uuid.uuid4()
        db_session.add(
            Material(
                id=material_id,
                name="Priced Steel",
                code="PRC-STL-01",
                category="steel",
                unit="kg",
                is_active=True,
            )
        )
        await db_session.commit()
        material = await db_session.get(Material, material_id)
        when = datetime.now(UTC)
        await materials_service.add_price(
            db_session, material, unit_price_minor=1000, currency="DZD", created_by=uuid.uuid4(), effective_from=when
        )
        with pytest.raises(ConflictError):
            await materials_service.add_price(
                db_session,
                material,
                unit_price_minor=2000,
                currency="DZD",
                created_by=uuid.uuid4(),
                effective_from=when,
            )
        # Session still usable: a later-dated price appends cleanly.
        await materials_service.add_price(
            db_session,
            material,
            unit_price_minor=2000,
            currency="DZD",
            created_by=uuid.uuid4(),
            effective_from=when + timedelta(days=1),
        )
        prices = await materials_service.list_prices(db_session, material_id=material_id)
        assert len(prices) == 2
