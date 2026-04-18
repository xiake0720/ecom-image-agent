"""SQLAlchemy 数据库类型适配。"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


UUID_TYPE = sa.Uuid(as_uuid=True)
INET_TYPE = postgresql.INET().with_variant(sa.String(length=45), "sqlite")
JSONB_TYPE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
