"""add pathway and pathway_parts tables

Revision ID: 0001_add_pathways
Revises:
Create Date: 2026-04-23

This is the first Alembic migration for the tenbio/pathwaysfinder API.
It ONLY creates the new pathway tables — your existing `parts` table is
left untouched (it was created via Base.metadata.create_all).

If you are adopting Alembic into an existing database, run once:

    alembic stamp head

before applying any further migrations, OR drop parts.db and let
Base.metadata.create_all + this migration rebuild from scratch.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_add_pathways"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pathways",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("host_organism", sa.String(length=50), nullable=True),
        sa.Column("plasmid_backbone", sa.String(length=100), nullable=True),
        sa.Column("selection_marker", sa.String(length=50), nullable=True),
        sa.Column("target_molecule", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("reference_doi", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathways_name", "pathways", ["name"])
    op.create_index("ix_pathways_host_organism", "pathways", ["host_organism"])
    op.create_index("ix_pathways_target_molecule", "pathways", ["target_molecule"])

    op.create_table(
        "pathway_parts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("pathway_id", sa.String(length=36),
                  sa.ForeignKey("pathways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(length=36),
                  sa.ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False, server_default="forward"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("pathway_id", "position", name="uq_pathway_position"),
    )
    op.create_index("ix_pathway_parts_pathway_id", "pathway_parts", ["pathway_id"])
    op.create_index("ix_pathway_parts_part_id", "pathway_parts", ["part_id"])


def downgrade() -> None:
    op.drop_index("ix_pathway_parts_part_id", table_name="pathway_parts")
    op.drop_index("ix_pathway_parts_pathway_id", table_name="pathway_parts")
    op.drop_table("pathway_parts")

    op.drop_index("ix_pathways_target_molecule", table_name="pathways")
    op.drop_index("ix_pathways_host_organism", table_name="pathways")
    op.drop_index("ix_pathways_name", table_name="pathways")
    op.drop_table("pathways")
