"""Initial database schema for EVE Healthcare

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-27 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="PATIENT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. diagnostic_centres table
    op.create_table(
        "diagnostic_centres",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnostic_centres_name"), "diagnostic_centres", ["name"], unique=False)
    op.create_index(
        op.f("ix_diagnostic_centres_is_active"),
        "diagnostic_centres",
        ["is_active"],
        unique=False,
    )

    # 3. diagnostic_tests table
    op.create_table(
        "diagnostic_tests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnostic_tests_name"), "diagnostic_tests", ["name"], unique=False)
    op.create_index(
        op.f("ix_diagnostic_tests_is_active"),
        "diagnostic_tests",
        ["is_active"],
        unique=False,
    )

    # 4. centre_tests association table
    op.create_table(
        "centre_tests",
        sa.Column("centre_id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["centre_id"], ["diagnostic_centres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_id"], ["diagnostic_tests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("centre_id", "test_id"),
    )

    # 5. bookings table
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("centre_id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["centre_id"], ["diagnostic_centres.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["test_id"], ["diagnostic_tests.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"], unique=False)
    op.create_index(op.f("ix_bookings_centre_id"), "bookings", ["centre_id"], unique=False)
    op.create_index(op.f("ix_bookings_test_id"), "bookings", ["test_id"], unique=False)
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"], unique=False)

    # 6. payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_booking_id"), "payments", ["booking_id"], unique=False)
    op.create_index(
        op.f("ix_payments_provider_payment_id"),
        "payments",
        ["provider_payment_id"],
        unique=True,
    )

    # 7. payment_webhook_events table (Database-level UNIQUE constraint on event_id for idempotency)
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_webhook_events_event_id"),
        "payment_webhook_events",
        ["event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_table("centre_tests")
    op.drop_table("diagnostic_tests")
    op.drop_table("diagnostic_centres")
    op.drop_table("users")
