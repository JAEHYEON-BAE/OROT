"""SQLAlchemy 선언적 기반 클래스.

제약·인덱스에 **결정론적 이름**을 부여한다. 이름이 자동 생성되면
Alembic 이 매번 다른 이름을 만들어 마이그레이션 차이가 불안정해진다.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# %(column_0_N_name)s 는 복합 인덱스에서 모든 컬럼명을 이어 붙인다.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """모든 ORM 모델의 기반."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
