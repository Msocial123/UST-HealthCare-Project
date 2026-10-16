"""Create patients table

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
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("medical_record_number", sa.String(length=14), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "sex IN ('FEMALE', 'MALE', 'OTHER', 'UNKNOWN')", name=op.f("ck_patients_sex_valid")
        ),
        sa.CheckConstraint("email IS NULL OR email = lower(email)", name=op.f("ck_patients_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patients")),
        sa.UniqueConstraint("medical_record_number", name=op.f("uq_patients_medical_record_number")),
    )
    op.create_index("ix_patients_last_name_lower", "patients", [sa.text("lower(last_name)")])
    op.create_index("ix_patients_first_name_lower", "patients", [sa.text("lower(first_name)")])
    op.create_index("ix_patients_date_of_birth", "patients", ["date_of_birth"])


def downgrade() -> None:
    op.drop_index("ix_patients_date_of_birth", table_name="patients")
    op.drop_index("ix_patients_first_name_lower", table_name="patients")
    op.drop_index("ix_patients_last_name_lower", table_name="patients")
    op.drop_table("patients")
