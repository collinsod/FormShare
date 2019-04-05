"""Changes in products table

Revision ID: 7f93d6af79d0
Revises: 8dea2dd6d509
Create Date: 2019-03-27 22:48:09.314042

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7f93d6af79d0'
down_revision = '8dea2dd6d509'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('created_by', sa.Unicode(length=120), nullable=False))
    op.add_column('product', sa.Column('output_file', sa.Unicode(length=120), nullable=True))
    op.alter_column('product', 'output_mimetype',
               existing_type=mysql.VARCHAR(length=120),
               nullable=True)
    op.create_index(op.f('ix_product_created_by'), 'product', ['created_by'], unique=False)
    op.create_index(op.f('ix_product_published_by'), 'product', ['published_by'], unique=False)
    op.create_foreign_key(op.f('fk_product_created_by_fsuser'), 'product', 'fsuser', ['created_by'], ['user_id'], ondelete='CASCADE')
    op.drop_column('product', 'process_name')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('process_name', mysql.VARCHAR(length=120), nullable=False))
    op.drop_constraint(op.f('fk_product_created_by_fsuser'), 'product', type_='foreignkey')
    op.drop_index(op.f('ix_product_published_by'), table_name='product')
    op.drop_index(op.f('ix_product_created_by'), table_name='product')
    op.alter_column('product', 'output_mimetype',
               existing_type=mysql.VARCHAR(length=120),
               nullable=False)
    op.drop_column('product', 'output_file')
    op.drop_column('product', 'created_by')
    # ### end Alembic commands ###