"""Widen overall_grade column and migrate to health tiers

Revision ID: 009_widen_overall_grade
Revises: 008_add_replay_tables
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_widen_overall_grade'
down_revision = '008_add_replay_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen column first (String(2) → String(10)) so new values fit
    op.alter_column(
        'workflow_quality_assessments', 'overall_grade',
        type_=sa.String(10),
        existing_type=sa.String(2),
        existing_nullable=False,
    )

    # Remap existing letter grades to health tiers based on overall_score
    op.execute("""
        UPDATE workflow_quality_assessments SET overall_grade =
        CASE
            WHEN overall_score >= 90 THEN 'Healthy'
            WHEN overall_score >= 70 THEN 'Degraded'
            WHEN overall_score >= 50 THEN 'At Risk'
            ELSE 'Critical'
        END
    """)


def downgrade() -> None:
    # Remap tiers back to letter grades
    op.execute("""
        UPDATE workflow_quality_assessments SET overall_grade =
        CASE
            WHEN overall_score >= 90 THEN 'A'
            WHEN overall_score >= 80 THEN 'B+'
            WHEN overall_score >= 70 THEN 'B'
            WHEN overall_score >= 60 THEN 'C+'
            WHEN overall_score >= 50 THEN 'C'
            WHEN overall_score >= 40 THEN 'D'
            ELSE 'F'
        END
    """)

    # Shrink column back
    op.alter_column(
        'workflow_quality_assessments', 'overall_grade',
        type_=sa.String(2),
        existing_type=sa.String(10),
        existing_nullable=False,
    )
