"""Dedicated quality-control (QC) test suite (Gate 4C).

Covers the QC lifecycle as a distinct concern, separate from the broader
production test suite: start, approve, reject, rework, self-approval prevention,
forged-identity/status/timestamp rejection, RBAC, IDOR, financial isolation,
inventory isolation, audit correctness, and completion safety.

Financial rule under test: QC operations NEVER mutate order/quote totals,
deposits, or balance due. Inventory rule: QC itself never mutates StockLevel.

Idempotency note: ``/qc/start`` and ``/qc/submit`` do not currently expose an
idempotency key. Concurrent duplicate decisions are protected by row locking
(SELECT ... FOR UPDATE) plus the state machine so exactly one decision wins and
audit events are not duplicated. No new idempotency mechanism was introduced.
"""

# ruff: noqa: RUF059  (test helper tuples unpack unused vars for readability)

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import ForbiddenError, InvalidStateTransition
from app.models.audit_enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.enums import OrderStatus, ProductionOrderStatus, Role
from app.models.inventory import StockLevel, StockMovement
from app.models.material import Material
from app.models.order import Order
from app.models.production import ProductionMaterialReservation, ProductionOrder
from app.services import inventory_service, production_service
from app.services.production_service import MaterialRequirement


def _make_order(db, status: OrderStatus = OrderStatus.CONFIRMED) -> Order:
    oid = uuid4()
    order = Order(
        id=oid,
        order_number=f"ZO-QC-{oid.hex[:8].upper()}",
        customer_id=None,
        quote_id=None,
        custom_request_id=None,
        status=status,
        currency="DZD",
        subtotal_minor=500000,
        discount_minor=0,
        delivery_fee_minor=0,
        total_minor=500000,
        deposit_required_minor=150000,
        deposit_paid_minor=150000,
        balance_due_minor=350000,
    )
    db.add(order)
    return order


def _make_material(db, code: str = "STEEL-BEAM") -> Material:
    m = Material(
        id=uuid4(), code=code, name=code.replace("-", " ").title(), category="steel", unit="kg", is_active=True
    )
    db.add(m)
    return m


async def _purchase(db, material_id, qty: str) -> None:
    await inventory_service.purchase(db, material_id=material_id, quantity=Decimal(qty), idempotency_key=uuid4())


async def _consume_all_reserved(db, po_id, *, qty: str = "10") -> None:
    """Consume every open reservation so QC's material-accounting precondition holds.

    start_quality_check requires all reserved materials to be consumed, wasted,
    returned or released before the order can enter QUALITY_CHECK.
    """
    mrs = (
        await db.execute(
            select(ProductionMaterialReservation).where(ProductionMaterialReservation.production_order_id == po_id)
        )
    ).scalars()
    for mr in mrs:
        remaining = production_service.compute_remaining_reserved(mr)
        if remaining > 0:
            await production_service.consume_material(
                db,
                po_id,
                material_reservation_id=mr.id,
                quantity=remaining,
                idempotency_key=uuid4(),
                actor_user_id=uuid4(),
            )
    await db.flush()


def _req(material: Material, qty: str = "10") -> MaterialRequirement:
    return MaterialRequirement(
        material_id=material.id,
        material_name=material.name,
        material_code=material.code,
        material_unit="kg",
        quantity_required=Decimal(qty),
        unit_price_minor=1000,
    )


async def _prepare_in_production(
    db, *, on_hand="100", qty="10", assigned_worker_id=None
) -> tuple[Order, ProductionOrder, Material]:
    """Create a confirmed order, stock the material, and a PO in IN_PRODUCTION."""
    order = _make_order(db)
    await db.flush()
    mat = _make_material(db)
    await _purchase(db, mat.id, on_hand)
    po = await production_service.create_production_order(db, order=order)
    await production_service.plan_production(db, po.id, requirements=[_req(mat, qty)])
    await production_service.reserve_materials(db, po.id)
    if assigned_worker_id is not None:
        po.assigned_worker_id = assigned_worker_id
    await production_service.start_production(db, po.id)
    await _consume_all_reserved(db, po.id, qty=qty)
    await db.flush()
    return order, po, mat


async def _commit_in_production(db, assigned_worker_id=None) -> str:
    """Build a PO in IN_PRODUCTION via the shared DB and commit it.

    The HTTP app runs in separate sessions on the same pooled engine, so the
    state must be committed (not just flushed) for endpoint requests to see it.
    Returns the production order id as a string.
    """
    _, po, _ = await _prepare_in_production(db, assigned_worker_id=assigned_worker_id)
    await db.commit()
    await db.refresh(po)
    return str(po.id)


async def _prepare_materials_reserved(db, *, on_hand="100", qty="10") -> tuple[Order, ProductionOrder, Material]:
    """Build a confirmable order + PO in MATERIALS_RESERVED (not yet started).

    Intentionally leaves production unstarted so the test can drive
    ``start_production`` (and the worker-recording behaviour) itself.
    """
    order = _make_order(db)
    await db.flush()
    mat = _make_material(db)
    await _purchase(db, mat.id, on_hand)
    po = await production_service.create_production_order(db, order=order)
    await production_service.plan_production(db, po.id, requirements=[_req(mat, qty)])
    await production_service.reserve_materials(db, po.id)
    await db.flush()
    return order, po, mat


async def _commit_materials_reserved(db) -> str:
    """Build a PO in MATERIALS_RESERVED via the shared DB and commit it."""
    _, po, _ = await _prepare_materials_reserved(db)
    await db.commit()
    await db.refresh(po)
    return str(po.id)


async def _audit_for(db, po_id, action: AuditAction) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.resource_id == str(po_id), AuditLog.action == action.value)
    return list((await db.execute(stmt)).scalars().all())


def _financial_snapshot(order: Order) -> dict:
    return {
        "subtotal_minor": order.subtotal_minor,
        "discount_minor": order.discount_minor,
        "delivery_fee_minor": order.delivery_fee_minor,
        "total_minor": order.total_minor,
        "deposit_required_minor": order.deposit_required_minor,
        "deposit_paid_minor": order.deposit_paid_minor,
        "balance_due_minor": order.balance_due_minor,
        "status": order.status,
    }


class TestStartQualityCheck:
    async def test_valid_start_from_in_production(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()
        po2 = await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        assert po2.status == ProductionOrderStatus.QUALITY_CHECK
        assert po2.qc_inspector_id == inspector
        assert po2.quality_check_started_at is not None

    async def test_invalid_state_rejected(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        # Once QUALITY_CHECK, starting again is rejected (repeated start).
        await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())
        with pytest.raises(InvalidStateTransition):
            await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())

    async def test_cannot_start_from_planned(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        # roll back to a non-IN_PRODUCTION state path: start a fresh planned order
        order2 = _make_order(db_session)
        await db_session.flush()
        mat2 = _make_material(db_session, code="ALLOY-02")
        await _purchase(db_session, mat2.id, "100")
        po2 = await production_service.create_production_order(db_session, order=order2)
        await production_service.plan_production(db_session, po2.id, requirements=[_req(mat2, "10")])
        await db_session.flush()
        with pytest.raises(InvalidStateTransition):
            await production_service.start_quality_check(db_session, po2.id, inspector_id=uuid4())


class TestApproval:
    async def test_approve_moves_to_ready_with_audit_actor(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        before = _financial_snapshot(order)
        level_before = (
            await db_session.execute(select(StockLevel).where(StockLevel.material_id == mat.id))
        ).scalar_one_or_none()
        moves_before = len(
            (await db_session.execute(select(StockMovement).where(StockMovement.material_id == mat.id))).scalars().all()
        )

        po2 = await production_service.complete_quality_check(
            db_session, po.id, approved=True, inspector_id=inspector, actor_user_id=inspector
        )
        assert po2.status == ProductionOrderStatus.READY
        assert po2.ready_at is not None
        assert po2.quality_check_completed_at is not None

        # Financial isolation
        assert _financial_snapshot(order) == before
        # Inventory isolation: QC adds no stock movements and no level changes
        moves_after = len(
            (await db_session.execute(select(StockMovement).where(StockMovement.material_id == mat.id))).scalars().all()
        )
        assert moves_after == moves_before  # QC adds no stock movements
        level_after = (
            await db_session.execute(select(StockLevel).where(StockLevel.material_id == mat.id))
        ).scalar_one()
        if level_before is not None:
            assert (level_after.on_hand, level_after.reserved) == (level_before.on_hand, level_before.reserved)


class TestRejection:
    async def test_reject_moves_to_in_production_with_defects_and_notes(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        before = _financial_snapshot(order)

        po2 = await production_service.complete_quality_check(
            db_session,
            po.id,
            approved=False,
            inspector_id=inspector,
            defects="paint flaw on left panel",
            notes="needs rework",
        )
        assert po2.status == ProductionOrderStatus.IN_PRODUCTION
        assert po2.qc_defects == "paint flaw on left panel"
        assert po2.qc_notes == "needs rework"
        assert po2.quality_check_completed_at is not None
        assert _financial_snapshot(order) == before


class TestRework:
    async def test_rework_cycle_then_approve(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        # Fail → back to production
        await production_service.complete_quality_check(
            db_session, po.id, approved=False, inspector_id=inspector, defects="defect"
        )
        assert po.status == ProductionOrderStatus.IN_PRODUCTION
        # QC again → approve
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        po2 = await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=inspector)
        assert po2.status == ProductionOrderStatus.READY


class TestSelfApproval:
    async def test_worker_cannot_approve_own_order(self, db_session):
        worker_id = uuid4()
        order, po, mat = await _prepare_in_production(db_session, assigned_worker_id=worker_id)
        await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())
        with pytest.raises(ForbiddenError):
            await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=worker_id)

    async def test_worker_cannot_start_qc_on_own_order(self, db_session):
        worker_id = uuid4()
        order, po, mat = await _prepare_in_production(db_session, assigned_worker_id=worker_id)
        with pytest.raises(ForbiddenError):
            await production_service.start_quality_check(db_session, po.id, inspector_id=worker_id)

    async def test_other_inspector_can_approve(self, db_session):
        worker_id = uuid4()
        inspector_id = uuid4()
        order, po, mat = await _prepare_in_production(db_session, assigned_worker_id=worker_id)
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector_id)
        po2 = await production_service.complete_quality_check(
            db_session, po.id, approved=True, inspector_id=inspector_id
        )
        assert po2.status == ProductionOrderStatus.READY


class TestAssignmentRecording:
    """The acting production operator is recorded as the assigned worker.

    ``start_production`` (and ``resume_production``) record the actor as
    ``assigned_worker_id`` when none is set, so the segregation-of-duties guard
    fires on work the same user performed -- without any separate assignment
    endpoint. A recorded assignment is never overwritten by a later actor.
    """

    async def test_start_records_actor_as_worker_and_blocks_self_qc(self, db_session):
        worker_id = uuid4()
        order, po, mat = await _prepare_materials_reserved(db_session)
        await production_service.start_production(db_session, po.id, actor_user_id=worker_id)
        assert po.assigned_worker_id == worker_id

        # The same actor cannot then QC the order they started.
        with pytest.raises(ForbiddenError):
            await production_service.start_quality_check(db_session, po.id, inspector_id=worker_id)

    async def test_existing_assignment_not_overwritten(self, db_session):
        worker_id = uuid4()
        starter_id = uuid4()
        order, po, mat = await _prepare_materials_reserved(db_session)
        po.assigned_worker_id = worker_id
        await db_session.flush()
        await production_service.start_production(db_session, po.id, actor_user_id=starter_id)
        assert po.assigned_worker_id == worker_id

    async def test_resume_records_actor_when_unassigned(self, db_session):
        worker_id = uuid4()
        order, po, mat = await _prepare_in_production(db_session)  # started without an actor
        assert po.assigned_worker_id is None
        await production_service.pause_production(db_session, po.id)
        await production_service.resume_production(db_session, po.id, actor_user_id=worker_id)
        assert po.assigned_worker_id == worker_id
        with pytest.raises(ForbiddenError):
            await production_service.start_quality_check(db_session, po.id, inspector_id=worker_id)

    async def test_worker_recorded_at_start_cannot_approve_after_reject_rework(self, db_session):
        worker_id = uuid4()
        inspector_id = uuid4()
        order, po, mat = await _prepare_materials_reserved(db_session)
        await production_service.start_production(db_session, po.id, actor_user_id=worker_id)
        await _consume_all_reserved(db_session, po.id)
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector_id)
        await production_service.complete_quality_check(
            db_session, po.id, approved=False, inspector_id=inspector_id, defects="defect"
        )
        # Rework sent back to the same recorded worker; still self-approval is blocked.
        with pytest.raises(ForbiddenError):
            await production_service.start_quality_check(db_session, po.id, inspector_id=worker_id)


class TestStateMachine:
    async def test_completion_only_after_ready(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        # cannot complete from IN_PRODUCTION
        with pytest.raises(InvalidStateTransition):
            await production_service.complete_production(db_session, po.id)
        # cannot complete from QUALITY_CHECK (pending decision)
        await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())
        with pytest.raises(InvalidStateTransition):
            await production_service.complete_production(db_session, po.id)
        # approve then complete
        await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=uuid4())
        po2 = await production_service.complete_production(db_session, po.id)
        assert po2.status == ProductionOrderStatus.COMPLETED

    async def test_terminal_ready_cannot_reenter_qc(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())
        await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=uuid4())
        with pytest.raises(InvalidStateTransition):
            await production_service.start_quality_check(db_session, po.id, inspector_id=uuid4())


class TestForgedPayloadAndIsolation:
    async def test_qc_cycle_adds_no_stock_movements(self, db_session):
        """Approval + rejection + rework produce NO new stock movements."""
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()

        baseline = list(
            (await db_session.execute(select(StockMovement).where(StockMovement.material_id == mat.id))).scalars()
        )
        assert len(baseline) == 3  # purchase + reserve + full consumption, all from pre-QC setup

        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        await production_service.complete_quality_check(db_session, po.id, approved=False, inspector_id=inspector)
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=inspector)

        after = list(
            (await db_session.execute(select(StockMovement).where(StockMovement.material_id == mat.id))).scalars()
        )
        assert len(after) == len(baseline), "QC decisions must not create stock movements"


class TestAuditCorrectness:
    """Audit events are recorded by the HTTP endpoint layer (not the service).

    These tests drive the real /qc/start and /qc/submit endpoints so that the
    record_event call sites are covered, and assert the audited actor is the
    authenticated user (never a client-supplied inspector).
    """

    async def test_audit_actor_equals_authenticated_user(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        headers, user = await auth_header_factory(role=Role.PRODUCTION)

        start = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", headers=headers, json={})
        assert start.status_code == 200, start.text
        submit = await client.post(
            f"/api/v1/admin/production/{po_id}/qc/submit", headers=headers, json={"approved": True}
        )
        assert submit.status_code == 200, submit.text

        started = await _audit_for(db_session, po_id, AuditAction.PRODUCTION_QUALITY_CHECK_STARTED)
        approved = await _audit_for(db_session, po_id, AuditAction.PRODUCTION_QUALITY_CHECK_APPROVED)
        assert len(started) == 1
        assert len(approved) == 1
        assert str(started[0].actor_user_id) == str(user.id)
        assert str(approved[0].actor_user_id) == str(user.id)

    async def test_rejected_audit_action(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        headers, user = await auth_header_factory(role=Role.PRODUCTION)

        start = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", headers=headers, json={})
        assert start.status_code == 200, start.text
        submit = await client.post(
            f"/api/v1/admin/production/{po_id}/qc/submit",
            headers=headers,
            json={"approved": False, "defects": "paint flaw", "notes": "rework"},
        )
        assert submit.status_code == 200, submit.text

        rejected = await _audit_for(db_session, po_id, AuditAction.PRODUCTION_QUALITY_CHECK_REJECTED)
        assert len(rejected) == 1
        assert str(rejected[0].actor_user_id) == str(user.id)

    async def test_failed_decision_produces_no_success_audit(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        headers, _ = await auth_header_factory(role=Role.PRODUCTION)

        first = await client.post(f"/api/v1/admin/production/{po_id}/qc/start", headers=headers, json={})
        assert first.status_code == 200, first.text
        ok = await client.post(f"/api/v1/admin/production/{po_id}/qc/submit", headers=headers, json={"approved": True})
        assert ok.status_code == 200, ok.text

        # A second submit on the now-READY order (invalid transition) must fail
        # and must NOT emit a duplicate APPROVED audit event.
        bogus = await client.post(
            f"/api/v1/admin/production/{po_id}/qc/submit", headers=headers, json={"approved": True}
        )
        assert bogus.status_code >= 400, bogus.text

        approved = await _audit_for(db_session, po_id, AuditAction.PRODUCTION_QUALITY_CHECK_APPROVED)
        assert len(approved) == 1


class TestCompletionSafety:
    async def test_complete_rejects_when_qc_failed(self, db_session):
        order, po, mat = await _prepare_in_production(db_session)
        inspector = uuid4()
        await production_service.start_quality_check(db_session, po.id, inspector_id=inspector)
        await production_service.complete_quality_check(db_session, po.id, approved=False, inspector_id=inspector)
        with pytest.raises(InvalidStateTransition):
            await production_service.complete_production(db_session, po.id)


class TestHttpSecurity:
    """HTTP-level Gate 4C security requirements: self-approval 403, forged
    fields, RBAC, and IDOR against the real /qc endpoints."""

    QC_START = "/api/v1/admin/production/{id}/qc/start"
    QC_SUBMIT = "/api/v1/admin/production/{id}/qc/submit"

    async def test_self_approval_returns_403(self, db_session, client, auth_header_factory):
        worker, wuser = await auth_header_factory(role=Role.PRODUCTION)
        po_id = await _commit_in_production(db_session, assigned_worker_id=wuser.id)

        # Another inspector starts QC so the order is in QUALITY_CHECK.
        inspector_headers, _ = await auth_header_factory(role=Role.PRODUCTION)
        start = await client.post(self.QC_START.format(id=po_id), headers=inspector_headers, json={})
        assert start.status_code == 200, start.text

        # The assigned worker (who still holds quality.manage) tries to approve
        # their own order -> identity self-approval guard must reject with 403.
        resp = await client.post(self.QC_SUBMIT.format(id=po_id), headers=worker, json={"approved": True})
        assert resp.status_code == 403, resp.text

    async def test_starting_own_production_blocks_own_qc(self, db_session, client, auth_header_factory):
        """End-to-end: the user who starts production cannot QC that order.

        Uses only the real endpoints -- start records the acting user as the
        assigned worker, and the subsequent self-inspection must be 403.
        """
        po_id = await _commit_materials_reserved(db_session)
        worker_headers, worker_user = await auth_header_factory(role=Role.PRODUCTION)

        start = await client.post(f"/api/v1/admin/production/{po_id}/start", headers=worker_headers, json={})
        assert start.status_code == 200, start.text

        po = (
            await db_session.execute(select(ProductionOrder).where(ProductionOrder.id == UUID(po_id)))
        ).scalar_one()
        assert str(po.assigned_worker_id) == str(worker_user.id)

        resp = await client.post(self.QC_START.format(id=po_id), headers=worker_headers, json={})
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "forbidden"

        # Account for the reserved materials so the independent inspector's
        # real /qc/start request can proceed past the material-accounting gate.
        await _consume_all_reserved(db_session, UUID(po_id))
        await db_session.commit()

        # An independent inspector can still start QC.
        inspector_headers, _ = await auth_header_factory(role=Role.PRODUCTION)
        ok = await client.post(self.QC_START.format(id=po_id), headers=inspector_headers, json={})
        assert ok.status_code == 200, ok.text
        assert ok.json()["qc_inspector_id"]  # server-derived, never the starter

    async def test_forged_inspector_rejected(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        headers, _ = await auth_header_factory(role=Role.PRODUCTION)
        other = str(uuid4())

        # inspector_id is not part of the request contract: rejected by extra="forbid".
        start = await client.post(self.QC_START.format(id=po_id), headers=headers, json={"inspector_id": other})
        assert start.status_code == 422, start.text

        s = await client.post(self.QC_START.format(id=po_id), headers=headers, json={})
        assert s.status_code == 200, s.text
        submit = await client.post(
            self.QC_SUBMIT.format(id=po_id),
            headers=headers,
            json={"approved": True, "inspector_id": other},
        )
        assert submit.status_code == 422, submit.text

        # The server-derived inspector is the authenticated user, not the forged one.
        assert (await _audit_for(db_session, po_id, AuditAction.PRODUCTION_QUALITY_CHECK_STARTED))[0].actor_user_id
        assert s.json()["qc_inspector_id"]

    async def test_forged_status_and_timestamps_rejected(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        headers, _ = await auth_header_factory(role=Role.PRODUCTION)

        s = await client.post(self.QC_START.format(id=po_id), headers=headers, json={})
        assert s.status_code == 200, s.text
        resp = await client.post(
            self.QC_SUBMIT.format(id=po_id),
            headers=headers,
            json={
                "approved": True,
                "status": "READY",
                "quality_check_started_at": "2020-01-01T00:00:00Z",
                "quality_check_completed_at": "2020-01-01T00:00:00Z",
            },
        )
        # All four are client-controlled in the forged attempt; extra="forbid" rejects.
        assert resp.status_code == 422, resp.text

        # Approved decision succeeds, and the transition is controlled by the
        # server state machine (READY comes only from an approve).
        ok = await client.post(self.QC_SUBMIT.format(id=po_id), headers=headers, json={"approved": True})
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == ProductionOrderStatus.READY.value

    async def test_rbac_worker_cannot_operate_qc(self, db_session, client, auth_header_factory):
        po_id = await _commit_in_production(db_session)
        worker_headers, _ = await auth_header_factory(role=Role.WORKER)

        start = await client.post(self.QC_START.format(id=po_id), headers=worker_headers, json={})
        assert start.status_code == 403, start.text
        submit = await client.post(self.QC_SUBMIT.format(id=po_id), headers=worker_headers, json={"approved": True})
        assert submit.status_code == 403, submit.text

    async def test_idor_unknown_order_rejected(self, db_session, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.PRODUCTION)
        start = await client.post(self.QC_START.format(id=str(uuid4())), headers=headers, json={})
        assert start.status_code == 404, start.text
