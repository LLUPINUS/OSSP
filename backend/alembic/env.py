from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 우리 프로젝트의 설정과 모델 import
from app.core.config import settings
from app.core.database import Base
from app.models import (  # noqa: F401  (Alembic 자동 감지용)
    Recipe,
    Transcript,
    ActionLabel,
    CookingStep,
)

# Alembic Config 객체 (alembic.ini 접근용)
config = context.config

# alembic.ini에 sqlalchemy.url이 비어있으므로 .env에서 읽어와 동적으로 설정
# Alembic은 동기 드라이버(psycopg2)를 사용
config.set_main_option("sqlalchemy.url", settings.ALEMBIC_DATABASE_URL)

# 로깅 설정 (alembic.ini의 [loggers] 섹션 사용)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic이 모델 변경을 감지하는 기준이 되는 metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    오프라인 모드: DB에 연결하지 않고 SQL 스크립트만 생성.
    `alembic upgrade head --sql` 같은 명령어용. 우리는 거의 안 씀.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드: 실제 DB에 연결해서 마이그레이션 실행."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 컬럼 타입 변경도 감지
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()