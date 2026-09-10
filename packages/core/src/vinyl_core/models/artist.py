"""아티스트 (블루프린트 §4.2)."""

import uuid

from sqlalchemy import BigInteger, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vinyl_core.models.base import Base


class Artist(Base):
    """아티스트. `name_norm` 이 병합 키이며 유일하다."""

    __tablename__ = "artists"
    __table_args__ = (
        UniqueConstraint("name_norm", name="uq_artists_name_norm"),
        # 한글/영문 교차 검색(§5.2 /v1/search)을 위한 trigram 인덱스.
        Index(
            "ix_artists_name_norm_trgm",
            "name_norm",
            postgresql_using="gin",
            postgresql_ops={"name_norm": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name_display: Mapped[str] = mapped_column(Text, nullable=False)
    name_ko: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False)
    mbid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
