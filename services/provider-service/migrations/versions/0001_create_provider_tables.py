"""Create specialties, providers and provider_specialties tables

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "specialties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_specialties_code_uppercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_specialties")),
        sa.UniqueConstraint("code", name=op.f("uq_specialties_code")),
        sa.UniqueConstraint("name", name=op.f("uq_specialties_name")),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_number", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("work_email", sa.String(length=254), nullable=False),
        sa.Column("work_phone", sa.String(length=32), nullable=False),
        sa.Column("license_number", sa.String(length=32), nullable=False),
        sa.Column("years_of_experience", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "years_of_experience >= 0 AND years_of_experience <= 70",
            name=op.f("ck_providers_years_of_experience_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_providers")),
        sa.UniqueConstraint("provider_number", name=op.f("uq_providers_provider_number")),
        sa.UniqueConstraint("license_number", name=op.f("uq_providers_license_number")),
    )
    op.create_index("ix_providers_last_name_first_name", "providers", ["last_name", "first_name"])
    op.create_table(
        "provider_specialties",
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("specialty_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
            name=op.f("fk_provider_specialties_provider_id_providers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["specialty_id"],
            ["specialties.id"],
            name=op.f("fk_provider_specialties_specialty_id_specialties"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("provider_id", "specialty_id", name=op.f("pk_provider_specialties")),
    )
    op.create_index("ix_provider_specialties_specialty_id", "provider_specialties", ["specialty_id"])
    op.create_index(
        "uq_provider_specialties_one_primary",
        "provider_specialties",
        ["provider_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        sqlite_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index("uq_provider_specialties_one_primary", table_name="provider_specialties")
    op.drop_index("ix_provider_specialties_specialty_id", table_name="provider_specialties")
    op.drop_table("provider_specialties")
    op.drop_index("ix_providers_last_name_first_name", table_name="providers")
    op.drop_table("providers")
    op.drop_table("specialties")
