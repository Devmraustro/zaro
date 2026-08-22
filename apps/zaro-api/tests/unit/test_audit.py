import uuid

import pytest
from sqlalchemy import select

from app.models.audit_enums import AuditAction, AuditResult
from app.models.audit_log import AuditLog
from app.models.enums import Role
from app.services.audit import _sanitize_metadata, record_event


def _sanitized(metadata: dict):
    result = _sanitize_metadata(metadata)
    assert result is not None
    return result


class TestAuditActionCatalog:
    def test_all_expected_actions_exist(self):
        expected = {
            "AUTH_LOGIN_SUCCESS",
            "AUTH_LOGIN_FAILURE",
            "AUTH_LOGOUT",
            "AUTH_PASSWORD_CHANGE",
            "AUTH_REFRESH",
            "AUTH_REFRESH_REUSE_DETECTED",
            "AUTH_PASSWORD_RESET_REQUESTED",
            "AUTH_PASSWORD_RESET_COMPLETED",
            "AUTH_SESSION_REVOKED",
            "AUTH_ALL_SESSIONS_REVOKED",
            "ACCOUNT_DISABLED",
            "ACCOUNT_ENABLED",
            "USER_CREATED",
            "USER_UPDATED",
            "USER_DISABLED",
            "USER_ROLE_CHANGED",
            "PERMISSION_DENIED",
            "PAYMENT_CREATED",
            "PAYMENT_PROOF_UPLOADED",
            "PAYMENT_SUBMITTED_FOR_REVIEW",
            "PAYMENT_CONFIRMED",
            "PAYMENT_REJECTED",
            "PAYMENT_CONFIGURATION_CHANGED",
            "QUOTE_CREATED",
            "QUOTE_SENT",
            "QUOTE_VIEWED",
            "QUOTE_ACCEPTED",
            "QUOTE_REJECTED",
            "QUOTE_CANCELLED",
            "QUOTE_EXPIRED",
            "ORDER_CREATED",
            "ORDER_STATUS_CHANGED",
            "ORDER_CANCELLED",
            "PRODUCT_CREATED",
            "PRODUCT_UPDATED",
            "PRODUCT_PRICE_CHANGED",
            "FILE_UPLOADED",
            "FILE_DELETED",
            "SECURITY_SETTING_CHANGED",
        }
        actual = {action.value for action in AuditAction}
        assert expected <= actual

    def test_actions_are_strings(self):
        for action in AuditAction:
            assert isinstance(action.value, str)
            assert action.value == action.value.upper()

    def test_action_count(self):
        assert len(AuditAction) >= 20


class TestAuditResult:
    def test_all_results_exist(self):
        expected = {"SUCCESS", "FAILURE", "DENIED"}
        actual = {r.value for r in AuditResult}
        assert expected == actual

    def test_results_are_strings(self):
        for result in AuditResult:
            assert isinstance(result.value, str)


class TestAuditEventCreation:
    @pytest.mark.asyncio
    async def test_record_event_creates_audit_log(self, db_session):
        actor_id = uuid.uuid4()
        event = await record_event(
            db_session,
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            result=AuditResult.SUCCESS,
            actor_user_id=actor_id,
            request_id="req-test-001",
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            metadata={"email": "test@example.com"},
        )
        assert event.id is not None
        assert event.action == "AUTH_LOGIN_SUCCESS"
        assert event.result == "SUCCESS"
        assert event.actor_user_id == actor_id
        assert event.request_id == "req-test-001"
        assert event.ip_address == "127.0.0.1"
        assert event.user_agent == "TestAgent/1.0"
        assert event.metadata_json is not None
        assert event.metadata_json["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_record_event_with_none_actor(self, db_session):
        event = await record_event(
            db_session,
            action=AuditAction.AUTH_LOGIN_FAILURE,
            result=AuditResult.FAILURE,
            metadata={"reason": "invalid_password"},
        )
        assert event.actor_user_id is None
        assert event.action == "AUTH_LOGIN_FAILURE"

    @pytest.mark.asyncio
    async def test_record_event_with_resource(self, db_session):
        resource_id = str(uuid.uuid4())
        event = await record_event(
            db_session,
            action=AuditAction.ORDER_CREATED,
            result=AuditResult.SUCCESS,
            actor_user_id=uuid.uuid4(),
            resource_type="order",
            resource_id=resource_id,
        )
        assert event.resource_type == "order"
        assert event.resource_id == resource_id

    @pytest.mark.asyncio
    async def test_record_event_persists_to_database(self, db_session):
        actor_id = uuid.uuid4()
        await record_event(
            db_session,
            action=AuditAction.PRODUCT_CREATED,
            result=AuditResult.SUCCESS,
            actor_user_id=actor_id,
        )
        await db_session.flush()

        result = await db_session.execute(select(AuditLog).where(AuditLog.actor_user_id == actor_id))
        events = result.scalars().all()
        assert len(events) == 1
        assert events[0].action == "PRODUCT_CREATED"


class TestAuditMetadataSanitization:
    def test_password_is_redacted(self):
        metadata = {"password": "secret123", "email": "test@example.com"}
        sanitized = _sanitized(metadata)
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["email"] == "test@example.com"

    def test_token_is_redacted(self):
        metadata = {"token": "eyJhbGciOiJIUzI1NiJ9.test.signature"}
        sanitized = _sanitized(metadata)
        assert sanitized["token"] == "[REDACTED]"

    def test_secret_key_is_redacted(self):
        metadata = {"secret_key": "my-secret-key"}
        sanitized = _sanitized(metadata)
        assert sanitized["secret_key"] == "[REDACTED]"

    def test_api_key_is_redacted(self):
        metadata = {"api_key": "sk-12345"}
        sanitized = _sanitized(metadata)
        assert sanitized["api_key"] == "[REDACTED]"

    def test_refresh_token_is_redacted(self):
        metadata = {"refresh_token": "rt-abc123"}
        sanitized = _sanitized(metadata)
        assert sanitized["refresh_token"] == "[REDACTED]"

    def test_credit_card_is_redacted(self):
        metadata = {"card_number": "4111111111111111", "cvv": "123"}
        sanitized = _sanitized(metadata)
        assert sanitized["card_number"] == "[REDACTED]"
        assert sanitized["cvv"] == "[REDACTED]"

    def test_none_metadata_returns_none(self):
        assert _sanitize_metadata(None) is None

    def test_empty_metadata_returns_none(self):
        assert _sanitize_metadata({}) is None

    def test_long_strings_are_truncated(self):
        metadata = {"long_field": "a" * 5000}
        sanitized = _sanitized(metadata)
        assert len(sanitized["long_field"]) <= 1000

    def test_numeric_values_preserved(self):
        metadata = {"count": 42, "rate": 3.14, "active": True}
        sanitized = _sanitized(metadata)
        assert sanitized["count"] == 42
        assert sanitized["rate"] == 3.14
        assert sanitized["active"] is True

    def test_nested_dict_sanitized(self):
        metadata = {"nested": {"password": "secret", "name": "test"}}
        sanitized = _sanitized(metadata)
        assert sanitized["nested"]["password"] == "[REDACTED]"
        assert sanitized["nested"]["name"] == "test"

    def test_case_insensitive_redaction(self):
        metadata = {"Password": "secret", "SECRET_KEY": "key", "api_key": "key123"}
        sanitized = _sanitized(metadata)
        assert sanitized["Password"] == "[REDACTED]"
        assert sanitized["SECRET_KEY"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"


class TestAuditImmutability:
    @pytest.mark.asyncio
    async def test_audit_log_has_no_update_mechanism_via_api(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.put(
            "/api/v1/audit/logs/some-id",
            headers=headers,
            json={"action": "MODIFIED"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_audit_log_has_no_delete_mechanism_via_api(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.delete(
            "/api/v1/audit/logs/some-id",
            headers=headers,
        )
        assert response.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_audit_log_has_no_patch_mechanism_via_api(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.patch(
            "/api/v1/audit/logs/some-id",
            headers=headers,
            json={"result": "SUCCESS"},
        )
        assert response.status_code in (404, 405)


class TestAuditAdminEndpoint:
    @pytest.mark.asyncio
    async def test_audit_logs_requires_permission(self, client):
        response = await client.get("/api/v1/audit/logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_worker_denied_audit_logs(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.WORKER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_can_list_audit_logs(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_audit_logs_supports_pagination(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get(
            "/api/v1/audit/logs?page=1&page_size=5",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    @pytest.mark.asyncio
    async def test_audit_logs_supports_action_filter(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get(
            "/api/v1/audit/logs?action=PERMISSION_DENIED",
            headers=headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_logs_rejects_invalid_page(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get(
            "/api/v1/audit/logs?page=0",
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_audit_logs_rejects_oversized_page(self, client, auth_header_factory):
        headers, _ = await auth_header_factory(role=Role.OWNER)
        response = await client.get(
            "/api/v1/audit/logs?page_size=999",
            headers=headers,
        )
        assert response.status_code == 422


class TestDeniedActionAuditLogging:
    @pytest.mark.asyncio
    async def test_permission_denial_creates_correct_event(self, client, auth_header_factory, db_session):
        from sqlalchemy import select as sa_select

        headers, user = await auth_header_factory(role=Role.CUSTOMER)
        response = await client.get("/api/v1/audit/logs", headers=headers)
        assert response.status_code == 403

        result = await db_session.execute(
            sa_select(AuditLog).where(
                AuditLog.actor_user_id == user.id,
                AuditLog.action == AuditAction.PERMISSION_DENIED.value,
            )
        )
        events = result.scalars().all()
        assert len(events) >= 1
        event = events[-1]
        assert event.result == AuditResult.DENIED.value
        assert event.resource_type == "audit"
        assert event.metadata_json is not None
        assert event.metadata_json["required_permission"] == "audit.read"
