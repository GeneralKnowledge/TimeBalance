"""Alembic environment. The engine is passed in by ``mpe.storage.database.upgrade``."""

from alembic import context

from mpe.storage.orm import Base

config = context.config
target_metadata = Base.metadata


def run() -> None:
    engine = config.attributes.get("engine")
    if engine is None:
        from mpe.config import load_settings
        from mpe.storage.database import make_engine

        engine = make_engine(load_settings().database_path)
    with engine.begin() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        context.run_migrations()


run()
