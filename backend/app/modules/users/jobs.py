import logging
import uuid

from app.jobs.registry import job_handler
from app.modules.users.service import storage_prefix
from app.storage import get_storage

logger = logging.getLogger(__name__)


@job_handler("user.purge_storage")
async def purge_storage(session, payload, job) -> None:
    removed = await get_storage().delete_prefix(storage_prefix(uuid.UUID(payload["user_id"])))
    logger.info("user_storage_purged", extra={"extra_fields": {"files": removed}})
