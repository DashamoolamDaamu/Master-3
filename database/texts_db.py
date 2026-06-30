# database/texts_db.py
# Persistence layer for admin-editable bot text overrides.
#
# Stores {key: value} overrides so the owner can edit any bot message from
# the /admin Telegram panel and have it apply instantly + survive restarts.
#
# Backend: MongoDB collection "bot_texts" when the project is running on
# Mongo (db.use_mongo). Falls back to a local JSON file when running on the
# PostgreSQL backend, so persistence still works either way.

import json
import logging
import os
import time

from database.users_chats_db import db

logger = logging.getLogger(__name__)

_FALLBACK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_FALLBACK_FILE = os.path.join(_FALLBACK_PATH, "bot_texts.json")


def _mongo_col():
    if db.use_mongo:
        return db.db.bot_texts
    return None


def _file_read() -> dict:
    try:
        if not os.path.exists(_FALLBACK_FILE):
            return {}
        with open(_FALLBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("texts_db: failed reading fallback file: %s", e)
        return {}


def _file_write(data: dict) -> None:
    try:
        os.makedirs(_FALLBACK_PATH, exist_ok=True)
        with open(_FALLBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("texts_db: failed writing fallback file: %s", e)


async def get_all() -> dict:
    """Return {key: value} for every overridden text."""
    col = _mongo_col()
    if col is not None:
        try:
            out = {}
            async for doc in col.find({}):
                out[doc["_id"]] = doc.get("value", "")
            return out
        except Exception as e:
            logger.exception("texts_db.get_all (mongo) failed: %s", e)
            return {}
    return _file_read()


async def get(key: str):
    """Return the override for `key`, or None if not overridden."""
    col = _mongo_col()
    if col is not None:
        try:
            doc = await col.find_one({"_id": key})
            return doc.get("value") if doc else None
        except Exception as e:
            logger.exception("texts_db.get (mongo) failed: %s", e)
            return None
    return _file_read().get(key)


async def set(key: str, value: str) -> None:
    """Persist an override for `key`."""
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
            logger.exception("texts_db.set (mongo) failed: %s", e)
            return
    data = _file_read()
    data[key] = value
    _file_write(data)


async def reset(key: str) -> None:
    """Remove the override for `key` (reverts to hardcoded default)."""
    col = _mongo_col()
    if col is not None:
        try:
            await col.delete_one({"_id": key})
            return
        except Exception as e:
            logger.exception("texts_db.reset (mongo) failed: %s", e)
            return
    data = _file_read()
    data.pop(key, None)
    _file_write(data)


async def reset_all() -> None:
    col = _mongo_col()
    if col is not None:
        try:
            await col.delete_many({})
            return
        except Exception as e:
            logger.exception("texts_db.reset_all (mongo) failed: %s", e)
            return
    _file_write({})
