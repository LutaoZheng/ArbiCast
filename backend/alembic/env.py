import asyncio
from alembic import context
from app.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata=Base.metadata
def offline():
    context.configure(url=get_settings().database_url,target_metadata=target_metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
def run_migrations(connection):
    context.configure(connection=connection,target_metadata=target_metadata)
    with context.begin_transaction():context.run_migrations()
async def online():
    engine=create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:await connection.run_sync(run_migrations)
    await engine.dispose()
if context.is_offline_mode():offline()
else:asyncio.run(online())
