"""Unit tests for the payment domain: transitions, configuration, claims."""

import pytest

from app.core.exceptions import InvalidStateTransition, ValidationFailedError
from app.models.enums import PaymentStatus
from app.services.payments_service import (
    REJECTION_REASON_CODES,
    validate_transition,
)


class TestPaymentStateMachine:
    def test_customer_path_forward(self):
        validate_transition(PaymentStatus.PENDING, PaymentStatus.PROOF_UPLOADED)
        validate_transition(PaymentStatus.PROOF_UPLOADED, PaymentStatus.UNDER_REVIEW)
        validate_transition(PaymentStatus.UNDER_REVIEW, PaymentStatus.CONFIRMED)

    def test_resubmission_after_rejection(self):
        validate_transition(PaymentStatus.REJECTED, PaymentStatus.PROOF_UPLOADED)
        validate_transition(PaymentStatus.PROOF_UPLOADED, PaymentStatus.UNDER_REVIEW)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            # Confirmation is irreversible -- no generic CONFIRMED -> anything.
            (PaymentStatus.CONFIRMED, PaymentStatus.REJECTED),
            (PaymentStatus.CONFIRMED, PaymentStatus.UNDER_REVIEW),
            (PaymentStatus.CONFIRMED, PaymentStatus.CANCELLED),
            # Reviewer cannot reject a claim the customer never submitted.
            (PaymentStatus.PENDING, PaymentStatus.CONFIRMED),
            (PaymentStatus.PENDING, PaymentStatus.REJECTED),
            (PaymentStatus.PROOF_UPLOADED, PaymentStatus.CONFIRMED),
            # Cancelled claims stay closed.
            (PaymentStatus.CANCELLED, PaymentStatus.PENDING),
            (PaymentStatus.REJECTED, PaymentStatus.CONFIRMED),
        ],
    )
    def test_invalid_transitions_rejected(self, current, target):
        with pytest.raises(InvalidStateTransition):
            validate_transition(current, target)


class TestConfigurationValidation:
    @pytest.mark.asyncio
    async def test_update_rejects_bad_percentage(self, db_session):
        from app.services import payments_service

        with pytest.raises(ValidationFailedError):
            await payments_service.update_configuration(db_session, default_deposit_percentage=0)
        with pytest.raises(ValidationFailedError):
            await payments_service.update_configuration(db_session, default_deposit_percentage=101)
        with pytest.raises(ValidationFailedError):
            await payments_service.update_configuration(db_session, account_holder="Z")
        with pytest.raises(ValidationFailedError):
            await payments_service.update_configuration(db_session, account_identifier="")

    @pytest.mark.asyncio
    async def test_configuration_is_singleton(self, db_session):
        from sqlalchemy import select

        from app.models.payment import PaymentConfiguration
        from app.services import payments_service

        first = await payments_service.get_configuration(db_session)
        second = await payments_service.get_configuration(db_session)
        assert first.id == second.id
        rows = list((await db_session.execute(select(PaymentConfiguration))).scalars().all())
        assert len(rows) == 1


class TestRejectionReasons:
    def test_expected_codes(self):
        assert {
            "proof_unreadable",
            "incorrect_amount",
            "incorrect_recipient",
            "duplicate_transfer",
            "invalid_proof",
        } <= REJECTION_REASON_CODES


class TestClaimAmountAuthority:
    @pytest.mark.asyncio
    async def test_claim_amount_always_from_order(self, db_session):
        """A deposit claim's amount is copied from order.deposit_required_minor;
        there is no parameter through which a client could alter it."""
        import inspect

        from app.services import payments_service

        signature = inspect.signature(payments_service.create_deposit_claim)
        assert "amount" not in signature.parameters
        assert "amount_minor" not in signature.parameters
        assert set(signature.parameters) == {"db", "order", "customer_id"}

    @pytest.mark.asyncio
    async def test_confirm_locks_rows_before_mutation(self, db_session):
        import inspect

        from app.services import payments_service

        src = inspect.getsource(payments_service.confirm_payment)
        assert "with_for_update" in src


class TestBl03LockOrder:
    """Guard the global Payment -> Order -> Quote lock order shared by
    confirm_payment and cancel_order_with_claim (BL-03). A future edit that
    locks Order before Payment re-introduces the 40P01 deadlock cycle; these
    source-level assertions pin the contract unit-level (the behavioural
    regression lives in test_pg_concurrency.py)."""

    @pytest.mark.asyncio
    async def test_confirm_payment_locks_payment_before_order(self, db_session):
        import inspect

        from app.services import payments_service

        src = inspect.getsource(payments_service.confirm_payment)
        assert src.index("get_for_update(db, payment_id)") < src.index("with_for_update()")
        assert src.index("with_for_update()") < src.index("apply_confirmed_deposit")

    @pytest.mark.asyncio
    async def test_cancel_order_with_claim_locks_payment_before_order(self, db_session):
        import inspect

        from app.services import orders_service

        src = inspect.getsource(orders_service.cancel_order_with_claim)
        payment_lock = src.index("select(Payment).where(Payment.id == active_claim.id).with_for_update()")
        order_lock = src.index("get_order_for_update(db, order_id)")
        assert payment_lock < order_lock
        assert "cancel_order(db, order, reason=reason)" in src
        assert src.index("with_for_update()") < src.index("PaymentStatus.CANCELLED")
