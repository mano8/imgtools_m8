"""api_key_rate_limit_redesign

Revision ID: 99540139637b
Revises: fb6ea2a0b401
Create Date: 2026-05-16 15:35:42.724526

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '99540139637b'
down_revision: Union[str, None] = 'fb6ea2a0b401'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ApiKey.id: AutoString (VARCHAR) → UUID
    op.alter_column(
        'auth_api_key', 'id',
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.Uuid(),
        existing_nullable=False,
    )

    # 2. Redesign auth_rate_limit: drop and recreate with the full new schema.
    #
    # Incremental ALTER TABLE (add column → make nullable → change ENUM → add FK)
    # triggers a COPY-algorithm rebuild for the ENUM change.  The COPY algorithm
    # renames the original .ibd file internally; a subsequent ADD FOREIGN KEY
    # then fails with errno 194 "Tablespace is missing" because the old
    # tablespace ID is stale after the rename.  DROP + CREATE TABLE writes a
    # fresh .ibd file, avoiding the issue entirely.
    op.drop_table('auth_rate_limit')
    op.create_table(
        'auth_rate_limit',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('api_key_id', sa.Uuid(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column(
            'period',
            sa.Enum('MINUTE', 'HOUR', 'DAY', 'MONTH', name='period'),
            nullable=False,
        ),
        sa.Column('limit', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['api_key_id'], ['auth_api_key.id'],
            name='fk_ratelimit_api_key_id', ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['auth_user.id'],
            name='fk_ratelimit_user_id', ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            'api_key_id IS NOT NULL OR user_id IS NOT NULL',
            name='ck_ratelimit_has_owner',
        ),
        sa.UniqueConstraint('api_key_id', 'period', name='uq_ratelimit_api_key_period'),
        sa.UniqueConstraint('user_id', 'period', name='uq_ratelimit_user_period'),
        mysql_charset='utf8mb4',
        mysql_engine='InnoDB',
    )
    op.create_index(
        op.f('ix_auth_rate_limit_api_key_id'), 'auth_rate_limit', ['api_key_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_rate_limit_user_id'), 'auth_rate_limit', ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    # Restore auth_rate_limit to the original single-user-id schema.
    op.drop_table('auth_rate_limit')
    op.create_table(
        'auth_rate_limit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column(
            'period',
            sa.Enum('MINUTE', 'HOUR', 'DAY', name='period'),
            nullable=False,
        ),
        sa.Column('limit', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['auth_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_engine='InnoDB',
    )
    op.create_index(
        op.f('ix_auth_rate_limit_user_id'), 'auth_rate_limit', ['user_id'],
        unique=False,
    )

    # Revert ApiKey.id: UUID → AutoString (VARCHAR)
    op.alter_column(
        'auth_api_key', 'id',
        existing_type=sa.Uuid(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=False,
    )
