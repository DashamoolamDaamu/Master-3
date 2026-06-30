# media_registry.py
# Central registry of bot media assets the owner can manage from
# /admin → Media Manager — uploaded once in Telegram, stored as file_id
# (no external hosting needed), applied instantly, persisted in MongoDB.
#
# Two slot kinds:
#   "pool"   -> a list of file_ids; one is chosen at random each send
#               (mirrors the existing PICS env-var pool, now owner-managed)
#   "single" -> one {"kind": "video"/"animation", "ref": file_id} value
#
# Like text_registry.py, slots that map onto an existing module-level
# constant (PICS) are kept live by monkeypatching the importing module's
# global — no call-site changes needed. Slots with no prior constant
# (welcome_media) are served through get_live_media() with a small,
# one-line edit at the single real call site.

import logging
import sys

import database.media_db as media_db

logger = logging.getLogger(__name__)

try:
    from info import PICS as _DEFAULT_PICS
except Exception:
    _DEFAULT_PICS = []

RUNTIME_DEFAULTS = {
    "welcome_media": {"kind": "video", "ref": "https://mangandi-2-0.onrender.com/Xdgv.mp4"},
}
RUNTIME_LIVE: dict = {k: dict(v) for k, v in RUNTIME_DEFAULTS.items()}


def get_live_media(key: str) -> dict:
    return RUNTIME_LIVE.get(key, RUNTIME_DEFAULTS.get(key, {}))


def _module_targets(attr: str):
    for modname in ("plugins.commands",):
        mod = sys.modules.get(modname)
        if mod is not None and hasattr(mod, attr):
            yield mod


SLOTS = [
    dict(
        key="start_photo", label="🖼 Start Photo Pool", kind="pool",
        accepts=("photo",), attr="PICS",
        help="Shown on /start in private chat. One photo is picked at random "
             "from the pool each time. Add as many as you like.",
    ),
    dict(
        key="welcome_media", label="🎬 Group Welcome Media", kind="single",
        accepts=("video", "animation"), attr=None,
        help="Sent automatically when a new member joins a group the bot is in.",
    ),
]
_BY_KEY = {s["key"]: s for s in SLOTS}


def get_slot(key: str):
    return _BY_KEY.get(key)


# ─────────────────────────────────────────────────────────────────────────────
# Current / default / apply
# ─────────────────────────────────────────────────────────────────────────────

def get_current_pool(key: str) -> list:
    slot = _BY_KEY.get(key)
    if not slot or slot["kind"] != "pool":
        return []
    for mod in _module_targets(slot["attr"]):
        return list(getattr(mod, slot["attr"]))
    return list(_DEFAULT_PICS)


def get_default_pool(key: str) -> list:
    slot = _BY_KEY.get(key)
    if slot and slot["key"] == "start_photo":
        return list(_DEFAULT_PICS)
    return []


def apply_pool(key: str, items: list) -> None:
    slot = _BY_KEY.get(key)
    if not slot:
        return
    for mod in _module_targets(slot["attr"]):
        setattr(mod, slot["attr"], list(items))


async def add_to_pool(key: str, file_id: str) -> list:
    items = await media_db.get(key)
    if not isinstance(items, list):
        items = []
    items.append(file_id)
    await media_db.set(key, items)
    apply_pool(key, items)
    return items


async def remove_last_from_pool(key: str) -> list:
    items = await media_db.get(key)
    if not isinstance(items, list) or not items:
        return items or []
    items = items[:-1]
    await media_db.set(key, items)
    if items:
        apply_pool(key, items)
    else:
        await media_db.reset(key)
        apply_pool(key, get_default_pool(key))
    return items


async def reset_pool(key: str) -> None:
    await media_db.reset(key)
    apply_pool(key, get_default_pool(key))


def get_current_single(key: str) -> dict:
    return get_live_media(key)


def get_default_single(key: str) -> dict:
    return dict(RUNTIME_DEFAULTS.get(key, {}))


async def save_single(key: str, kind: str, ref: str) -> None:
    value = {"kind": kind, "ref": ref}
    RUNTIME_LIVE[key] = value
    await media_db.set(key, value)


async def reset_single(key: str) -> None:
    RUNTIME_LIVE[key] = dict(RUNTIME_DEFAULTS.get(key, {}))
    await media_db.reset(key)


async def load_all_from_db() -> int:
    """Call once at bot startup, after DB connects."""
    count = 0
    try:
        overrides = await media_db.get_all()
    except Exception as e:
        logger.exception("media_registry: failed loading overrides: %s", e)
        return 0
    for key, value in overrides.items():
        slot = _BY_KEY.get(key)
        if not slot or value is None:
            continue
        if slot["kind"] == "pool" and isinstance(value, list):
            apply_pool(key, value)
            count += 1
        elif slot["kind"] == "single" and isinstance(value, dict):
            RUNTIME_LIVE[key] = value
            count += 1
    return count
