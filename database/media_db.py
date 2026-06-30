# database/media_db.py
# Persistence layer for admin-editable bot media (photos/videos/animations),
# stored as Telegram file_ids so no re-upload/hosting is needed.
#
# Mirrors database/texts_db.py: Mongo collection "bot_media" when running on
# Mongo, local JSON file fallback otherwise. Values are arbitrary JSON
# (a list for "pool" slots, a dict for "single" slots).

import json
import logging
import os
import time

from database.users_chats_db import db

logger = logging.getLogger(__name__)

_FALLBACK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_FALLBACK_FILE = os.path.join(_FALLBACK_PATH, "bot_media.json")


def _mongo_col():
    if db.use_mongo:
        return db.db.bot_media
    return None


def _file_read() -> dict:
    try:
        if not os.path.exists(_FALLBACK_FILE):
            return {}
        with open(_FALLBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("media_db: failed reading fallback file: %s", e)
        return {}


def _file_write(data: dict) -> None:
    try:
        os.makedirs(_FALLBACK_PATH, exist_ok=True)
        with open(_FALLBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("media_db: failed writing fallback file: %s", e)


async def get_all() -> dict:
    col = _mongo_col()
    if col is not None:
        try:
            out = {}
            async for doc in col.find({}):
                out[doc["_id"]] = doc.get("value")
            return out
        except Exception as e:
            logger.exception("media_db.get_all (mongo) failed: %s", e)
            return {}
    return _file_read()


async def get(key: str):
    col = _mongo_col()
    if col is not None:
        try:
            doc = await col.find_one({"_id": key})
            return doc.get("value") if doc else None
        except Exception as e:
            logger.exception("media_db.get (mongo) failed: %s", e)
            return None
    return _file_read().get(key)


async def set(key: str, value) -> None:
    col = _mongo_col()
    if col is not None:
        try:
            await col.update_one(
                {"_id": key},
                {"$set": {"value": value, "updated_at": time.time()}},
                upsert=True,
            )
            return
        except Exception as e:
            logger.exception("media_db.set (mongo) failed: %s", e)
            return
    data = _file_read()
    data[key] = value
    _file_write(data)


async def reset(key: str) -> None:
    col = _mongo_col()
    if col is not None:
        try:
            await col.delete_one({"_id": key})
            return
        except Exception as e:
            logger.exception("media_db.reset (mongo) failed: %s", e)
            return
    data = _file_read()
    data.pop(key, None)
    _file_write(data)
