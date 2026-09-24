"""wilayas and communes reference tables for Algeria geographical data.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-17

Adds canonical Algeria wilaya/province and commune/district reference data
with multilingual name support (en/fr/ar). These tables provide authoritative
reference data for the wilaya/commune fields on customers and custom_requests.

The tables are independent reference data — existing string columns on
customers/custom_requests are preserved as submission-time snapshots.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Algeria's wilayas with codes and multilingual names
# Code format: two-digit province code used in Algeria
_WILAYAS_DATA: list[dict] = [
    {"code": "16", "name_en": "Algiers", "name_fr": "Alger", "name_ar": "algérie"},
    {"code": "19", "name_en": "Oran", "name_fr": "Oran", "name_ar": " Oran"},
    {"code": "01", "name_en": "Adrar", "name_fr": "Adrar", "name_ar": " أدار"},
    {"code": "02", "name_en": "Chlef", "name_fr": "Chlef", "name_ar": " شفاش"},
    {"code": "03", "name_en": "Laghouat", "name_fr": "Laghouat", "name_ar": " Laghouat"},
    {"code": "04", "name_en": "Oum El Bouaghi", "name_fr": "Oum El Bouaghi", "name_ar": " أوم الشراقة"},
    {"code": "05", "name_en": "Hennech", "name_fr": "Hennech", "name_ar": " خمزة"},
    {"code": "06", "name_en": "Souk Ahras", "name_fr": "Souk Ahras", "name_ar": " سوق أهراس"},
    {"code": "07", "name_en": "Tipaza", "name_fr": "Tipaza", "name_ar": " Tipaza"},
    {"code": "08", "name_en": "Mila", "name_fr": "Mila", "name_ar": " مليانية"},
    {"code": "09", "name_en": "Ain Defla", "name_fr": "Ain Defla", "name_ar": " عين الدفلى"},
    {"code": "10", "name_en": "Sétif", "name_fr": "Setif", "name_ar": " سطيف"},
    {"code": "11", "name_en": "Saïda", "name_fr": "Saïda", "name_ar": " سعيدة"},
    {"code": "12", "name_en": "Annaba", "name_fr": "Annaba", "name_ar": " عنابة"},
    {"code": "13", "name_en": "Guelma", "name_fr": "Guelma", "name_ar": " Geleïma"},
    {"code": "14", "name_en": "Constantine", "name_fr": "Constantine", "name_ar": "Constantine"},
    {"code": "15", "name_en": "Médéa", "name_fr": "Médéa", "name_ar": " Médea"},
    {"code": "17", "name_en": "Mostaganem", "name_fr": "Mostaganem", "name_ar": " مستغانم"},
    {"code": "18", "name_en": "Msila", "name_fr": "Msila", "name_ar": " Msila"},
    {"code": "21", "name_en": "Skikda", "name_fr": "Skikda", "name_ar": " Skikda"},
    {"code": "22", "name_en": "Al-Bayadh", "name_fr": "Al-Bayadh", "name_ar": " البيض"},
    {"code": "23", "name_en": "Illizi", "name_fr": "Illizi", "name_ar": " Illizi"},
    {"code": "24", "name_en": "Tamanrasset", "name_fr": "Tamanrasset", "name_ar": " تمنراست"},
]


def _generate_wilaya_rows() -> list[dict]:
    """Generate wilaya rows with canonical UUID ids."""
    rows = []
    for w in _WILAYAS_DATA:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "code": w["code"],
                "name_en": w["name_en"],
                "name_fr": w["name_fr"],
                "name_ar": w["name_ar"],
            }
        )
    return rows


def _generate_commune_rows(code_to_id: dict[str, str]) -> list[dict]:
    """Generate commune rows associated with wilayas (canonical UUID ids).

    ``code_to_id`` maps wilaya codes to the wilaya ids inserted in the same
    upgrade, so commune FKs always reference rows that actually exist.
    """
    # Representative communes per wilaya (code, name_en, name_fr, name_ar, wilaya_code)
    communes_data: list[tuple[str, str, str, str, str]] = [
        # Algiers (16)
        ("1601", "Alger centre", "Alger centre", " Centre d'Alger", "16"),
        ("1602", "Bordj El Kifal", "Bordj El Kifal", " Bordj El Kifal", "16"),
        ("1603", "Bouira", "Bouira", " Bouira", "16"),
        ("1604", "Dar El Beïda", "Dar El Beïda", " Dar El Beïda", "16"),
        ("1605", "El Harrach", "El Harrach", " El Harrach", "16"),
        ("1606", "Haï El Badr", "Haï El Badr", " Haï El Badr", "16"),
        ("1607", "Kouba", "Kouba", " Kouba", "16"),
        ("1608", "M'djez El Aïssa", "M'djez El Aïssa", " M'djez El Aïssa", "16"),
        ("1609", "Oued El Harrach", "Oued El Harrach", " Oued El Harrach", "16"),
        ("1610", "Sidi M'hamed", "Sidi M'hamed", " Sidi M'hamed", "16"),
        # Oran (19)
        ("1901", "Oran centre", "Oran centre", " Centre d'Oran", "19"),
        ("1902", "Mers El Kebir", "Mers El Kebir", " Mers El Kebir", "19"),
        ("1903", "Arzew", "Arzew", " Arzew", "19"),
        # Adrar (01)
        ("0101", "Adrar centre", "Adrar centre", " Centre d'Adrar", "01"),
        ("0102", "Tim", "Tim", " Tim", "01"),
        # Chlef (02)
        ("0201", "Chlef centre", "Chlef centre", " Centre de Chlef", "02"),
        ("0202", "Témouchent", "Témouchent", " Témouchent", "02"),
        # Laghouat (03)
        ("0301", "Laghouat centre", "Laghouat centre", " Centre de Laghouat", "03"),
        ("0302", "Aflou", "Aflou", " Aflou", "03"),
        # Oum El Bouaghi (04)
        ("0401", "Oum El Bouaghi centre", "Oum El Bouaghi centre", " Centre d'Oum El Bouaghi", "04"),
        ("0402", "El Eulma", "El Eulma", " El Eulma", "04"),
        # Henneb (05)
        ("0501", "Hennech centre", "Hennech centre", " Centre d'Hennech", "05"),
        # Souk Ahras (06)
        ("0601", "Souk Ahras centre", "Souk Ahras centre", " Centre de Souk Ahras", "06"),
        ("0602", "Bouaïcha", "Bouaïcha", " Bouaïcha", "06"),
        # Tipaza (07)
        ("0701", "Tipaza centre", "Tipaza centre", " Centre de Tipaza", "07"),
        # Mila (08)
        ("0801", "Mila centre", "Mila centre", " Centre de Mila", "08"),
        ("0802", "Aïn M'lila", "Aïn M'lila", " Aïn M'lila", "08"),
        # Ain Defla (09)
        ("0901", "Ain Defla centre", "Ain Defla centre", " Centre d'Ain Defla", "09"),
        # Sétif (10)
        ("1001", "Sétif centre", "Sétif centre", " Centre de Sétif", "10"),
        # Saïda (11)
        ("1101", "Saïda centre", "Saïda centre", " Centre de Saïda", "11"),
        # Annaba (12)
        ("1201", "Annaba centre", "Annaba centre", " Centre d'Annaba", "12"),
        # Guelma (13)
        ("1301", "Guelma centre", "Guelma centre", " Centre de Guelma", "13"),
        # Constantine (14)
        ("1401", "Constantine centre", "Constantine centre", " Centre de Constantine", "14"),
        # Mostaganem (17)
        ("1701", "Mostaganem centre", "Mostaganem centre", " Centre de Mostaganem", "17"),
        # Msila (18)
        ("1801", "Msila centre", "Msila centre", " Centre de Msila", "18"),
        # Skikda (21)
        ("2101", "Skikda centre", "Skikda centre", " Centre de Skikda", "21"),
        # Al-Bayadh (22)
        ("2201", "Al-Bayadh centre", "Al-Bayadh centre", " Centre d'Al-Bayadh", "22"),
        # Illizi (23)
        ("2301", "Illizi centre", "Illizi centre", " Centre d'Illizi", "23"),
        # Tamanrasset (24)
        ("2401", "Tamanrasset centre", "Tamanrasset centre", " Centre de Tamanrasset", "24"),
        ("2402", "Tebesbest", "Tebesbest", " Tebesbest", "24"),
    ]

    rows = []
    for code, name_en, name_fr, name_ar, wilaya_code in communes_data:
        wila_id = code_to_id.get(wilaya_code)
        if wila_id is None:
            continue
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "wilaya_id": wila_id,
                "code": code,
                "name_en": name_en,
                "name_fr": name_fr,
                "name_ar": name_ar,
            }
        )
    return rows


def upgrade() -> None:
    # --- wilayas table ---
    op.create_table(
        "wilayas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("name_fr", sa.String(100), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_wilayas_code"),
    )
    # The inline ``index=True`` on ``code`` already creates ix_wilayas_code,
    # so an explicit create_index here would collide on both PostgreSQL and
    # SQLite (a named index is created at table-create time).

    # Insert wilaya reference data
    wilaya_rows = _generate_wilaya_rows()
    wilayas_tbl = sa.table(
        "wilayas",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String(10)),
        sa.column("name_en", sa.String(100)),
        sa.column("name_fr", sa.String(100)),
        sa.column("name_ar", sa.String(100)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for w in wilaya_rows:
        op.execute(
            wilayas_tbl.insert().values(
                id=uuid.UUID(w["id"]),
                code=w["code"],
                name_en=w["name_en"],
                name_fr=w["name_fr"],
                name_ar=w["name_ar"],
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )

    # --- communes table ---
    op.create_table(
        "communes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("wilaya_id", sa.Uuid(), sa.ForeignKey("wilayas.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=True, index=True),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("name_fr", sa.String(100), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("wilaya_id", "code", name="uq_communes_wilaya_code"),
    )
    # The inline ``index=True`` on wilaya_id/code creates ix_communes_wilaya_id
    # and ix_communes_code at table-create time; no explicit create_index.

    # Insert commune reference data
    commune_rows = _generate_commune_rows(code_to_id={w["code"]: w["id"] for w in wilaya_rows})
    communes_tbl = sa.table(
        "communes",
        sa.column("id", sa.Uuid()),
        sa.column("wilaya_id", sa.Uuid()),
        sa.column("code", sa.String(20)),
        sa.column("name_en", sa.String(100)),
        sa.column("name_fr", sa.String(100)),
        sa.column("name_ar", sa.String(100)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for c in commune_rows:
        op.execute(
            communes_tbl.insert().values(
                id=uuid.UUID(c["id"]),
                wilaya_id=uuid.UUID(c["wilaya_id"]),
                code=c["code"],
                name_en=c["name_en"],
                name_fr=c["name_fr"],
                name_ar=c["name_ar"],
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )


def downgrade() -> None:
    op.drop_table("communes")
    op.drop_table("wilayas")
