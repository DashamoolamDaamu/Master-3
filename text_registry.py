# text_registry.py
# Central registry of every bot-facing text message the owner can edit from
# the /admin → Text Manager panel.
#
# Each entry knows:
#   - where to read the CURRENT live value from
#   - how to APPLY a new value so it takes effect instantly, with no restart
#   - its ORIGINAL hardcoded default, so "Reset to Default" works
#
# Two kinds of entries:
#   1. "script" attrs   -> live on the `script` class (plugins read script.X
#                          directly at call-time, so setattr() is enough).
#   2. "module" globals -> a few plugin modules import a constant by name
#                          (e.g. `from info import CUSTOM_FILE_CAPTION`).
#                          Those become independent globals in each importing
#                          module, so we monkeypatch every module that holds
#                          one, instead of editing call sites.
#   3. "runtime" texts  -> new templates that didn't exist as named constants
#                          before (welcome caption, ban message, etc). Call
#                          sites were given a one-line edit to read these via
#                          get_live_text().

import logging

from Script import script
import database.texts_db as texts_db

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports of the few plugin modules whose globals we monkeypatch.
# Imported lazily (inside functions) to avoid import-order issues with
# Pyrogram's plugin auto-loader.
# ─────────────────────────────────────────────────────────────────────────────

def _module_targets(attr: str):
    """Yield every already-imported module object that holds a global named
    `attr` and should be kept in sync (e.g. CUSTOM_FILE_CAPTION)."""
    import sys
    for modname in (
        "plugins.pm_filter", "plugins.inline", "plugins.commands", "plugins.misc",
    ):
        mod = sys.modules.get(modname)
        if mod is not None and hasattr(mod, attr):
            yield mod


# ─────────────────────────────────────────────────────────────────────────────
# Runtime store for the brand-new templates (not previously named constants)
# ─────────────────────────────────────────────────────────────────────────────
RUNTIME_DEFAULTS = {
    "welcome_caption": (
        "<pre>ʜᴇʏ, {mention} 👋🏻\n"
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴏᴜʀ ɢʀᴏᴜᴘ {group}\n\n"
        "ʏᴏᴜ ᴄᴀɴ ꜰɪɴᴅ ᴍᴏᴠɪᴇꜱ / ꜱᴇʀɪᴇꜱ / ᴀɴɪᴍᴇꜱ ᴇᴛᴄ. ꜰʀᴏᴍ ʜᴇʀᴇ. ᴇɴᴊᴏʏ😉.</pre>"
    ),
    "ban_message": "Sorry Dude, You are Banned to use Me. \nBan Reason: {reason}",
    "disabled_chat_message": (
        "CHAT NOT ALLOWED 🐞\n\n"
        "My admins has restricted me from working here ! If you want to know "
        "more about it contact support..\nReason : <code>{reason}</code>."
    ),
}
RUNTIME_LIVE: dict = dict(RUNTIME_DEFAULTS)


def get_live_text(key: str) -> str:
    """Read current live value for a 'runtime' text key (with fallback)."""
    return RUNTIME_LIVE.get(key, RUNTIME_DEFAULTS.get(key, ""))


# ─────────────────────────────────────────────────────────────────────────────
# Capture ORIGINAL hardcoded defaults at first import, before anything has a
# chance to override them. Plugins (incl. admin.py) import this module while
# Pyrogram auto-loads plugins, which happens before Bot.start() applies any
# DB overrides — so this snapshot is guaranteed to be the untouched original.
# ─────────────────────────────────────────────────────────────────────────────
_SCRIPT_DEFAULTS = {}
_HELP_PAGES_DEFAULTS = list(getattr(script, "HELP_PAGES", []))

try:
    from info import CUSTOM_FILE_CAPTION as _DEFAULT_CUSTOM_FILE_CAPTION
except Exception:
    _DEFAULT_CUSTOM_FILE_CAPTION = ""
try:
    from info import IMDB_TEMPLATE as _DEFAULT_IMDB_TEMPLATE
except Exception:
    _DEFAULT_IMDB_TEMPLATE = ""


def _snap(attr):
    val = getattr(script, attr, "")
    _SCRIPT_DEFAULTS[attr] = val
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Registry definition
# entry: key, label, category, kind, variables (hint shown in preview)
#   kind == "script"  -> attr = Script class attribute name
#   kind == "page"    -> index into script.HELP_PAGES
#   kind == "module"  -> attr = global name patched across plugin modules
#   kind == "runtime" -> key into RUNTIME_LIVE / RUNTIME_DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = [
    ("core", "🚀 Core Messages"),
    ("help", "📖 Help & Filters"),
    ("search", "🔎 Search & Results"),
    ("group", "👋 Group & Moderation"),
    ("captions", "🏷 Captions & Templates"),
    ("logs", "📜 Log Channel Texts"),
]

ENTRIES = [
    # core
    dict(key="start", label="🚀 Start", category="core", kind="script", attr="START_TXT",
         variables="{0} = user mention"),
    dict(key="help_main", label="❓ Help (Header)", category="core", kind="script", attr="HELP_TXT",
         variables="{0} = user mention"),
    dict(key="about", label="ℹ️ About", category="core", kind="script", attr="ABOUT_TXT",
         variables="{0} = bot name"),
    dict(key="source", label="🧾 Source", category="core", kind="script", attr="SOURCE_TXT",
         variables="none"),
    dict(key="status", label="📊 Status", category="core", kind="script", attr="STATUS_TXT",
         variables="positional file/user/chat counters"),
    dict(key="restart", label="🔄 Restart (bot start)", category="core", kind="script", attr="RESTART_TXT",
         variables="none"),
    dict(key="restart_group", label="🔄 Restart (daily summary)", category="core", kind="script", attr="RESTART_GC_TXT",
         variables="{0} = date, {1} = time"),
]
for _i in range(1, 7):
    ENTRIES.append(dict(
        key=f"help_page_{_i}", label=f"❓ Help Page {_i}/6", category="core",
        kind="page", index=_i - 1, variables="static help page",
    ))

ENTRIES += [
    # help
    dict(key="manual_filter_help", label="🧩 Manual Filter Help", category="help", kind="script", attr="MANUELFILTER_TXT", variables="none"),
    dict(key="button_help", label="🔘 Button Help", category="help", kind="script", attr="BUTTON_TXT", variables="none"),
    dict(key="autofilter_help", label="🪄 AutoFilter Help", category="help", kind="script", attr="AUTOFILTER_TXT", variables="none"),
    dict(key="connection_help", label="🔗 Connection Help", category="help", kind="script", attr="CONNECTION_TXT", variables="none"),
    dict(key="extra_mod_help", label="➕ Extra Modules Help", category="help", kind="script", attr="EXTRAMOD_TXT", variables="none"),
    dict(key="admin_help", label="🛡 Admin Mods Help", category="help", kind="script", attr="ADMIN_TXT", variables="none"),

    # search
    dict(key="result_text", label="📦 Result Header", category="search", kind="script", attr="RESULT_TXT", variables="{mention} and other named fields"),
    dict(key="movie_not_found", label="🚫 Movie Not Found", category="search", kind="script", attr="MOV_NT_FND", variables="none"),
    dict(key="old_message", label="⏳ Old Message Notice", category="search", kind="script", attr="OLD_MES", variables="none"),
    dict(key="checking_alert", label="♻️ Checking Alert", category="search", kind="script", attr="CHK_MOV_ALRT", variables="none"),
    dict(key="spell_not_found", label="🔤 Spelling Not Found", category="search", kind="script", attr="SPOLL_NOT_FND", variables="none"),
    dict(key="spell_en", label="🇬🇧 Spell Tips (English)", category="search", kind="script", attr="ENG_SPELL", variables="none"),
    dict(key="spell_hi", label="🇮🇳 Spell Tips (Hindi)", category="search", kind="script", attr="HIN_SPELL", variables="none"),
    dict(key="spell_ta", label="🇮🇳 Spell Tips (Tamil)", category="search", kind="script", attr="TAM_SPELL", variables="none"),
    dict(key="spell_ml", label="🇮🇳 Spell Tips (Malayalam)", category="search", kind="script", attr="MAL_SPELL", variables="none"),

    # group / moderation (new, runtime-backed)
    dict(key="welcome_caption", label="👋 Group Welcome Caption", category="group", kind="runtime", variables="{mention}, {group}"),
    dict(key="ban_message", label="🚫 Ban Message", category="group", kind="runtime", variables="{reason}"),
    dict(key="disabled_chat_message", label="🔇 Disabled Chat Message", category="group", kind="runtime", variables="{reason}"),

    # captions / templates
    dict(key="custom_file_caption", label="🏷 File Caption Template", category="captions", kind="module", attr="CUSTOM_FILE_CAPTION", variables="{file_name}, {file_size}, {file_caption}"),
    dict(key="imdb_template", label="🎬 IMDb Caption Template", category="captions", kind="module", attr="IMDB_TEMPLATE", variables="{title}, {year}, {rating}, {genres}, {url} and more"),

    # logs
    dict(key="log_text_group", label="📜 New Group Log", category="logs", kind="script", attr="LOG_TEXT_G", variables="title, id, count, by"),
    dict(key="log_text_private", label="📜 New User Log", category="logs", kind="script", attr="LOG_TEXT_P", variables="positional user fields"),
]

_BY_KEY = {e["key"]: e for e in ENTRIES}


def get_entry(key: str):
    return _BY_KEY.get(key)


def entries_for_category(category: str):
    return [e for e in ENTRIES if e["category"] == category]


# ─────────────────────────────────────────────────────────────────────────────
# Current value / default value / apply
# ─────────────────────────────────────────────────────────────────────────────

def get_current(key: str) -> str:
    e = _BY_KEY.get(key)
    if not e:
        return ""
    if e["kind"] == "script":
        if e["attr"] not in _SCRIPT_DEFAULTS:
            _snap(e["attr"])
        return getattr(script, e["attr"], "")
    if e["kind"] == "page":
        pages = getattr(script, "HELP_PAGES", [])
        idx = e["index"]
        return pages[idx] if idx < len(pages) else ""
    if e["kind"] == "module":
        if e["attr"] == "CUSTOM_FILE_CAPTION":
            for mod in _module_targets("CUSTOM_FILE_CAPTION"):
                return getattr(mod, "CUSTOM_FILE_CAPTION")
            return _DEFAULT_CUSTOM_FILE_CAPTION
        if e["attr"] == "IMDB_TEMPLATE":
            for mod in _module_targets("IMDB_TEMPLATE"):
                return getattr(mod, "IMDB_TEMPLATE")
            return _DEFAULT_IMDB_TEMPLATE
    if e["kind"] == "runtime":
        return get_live_text(key)
    return ""


def get_default(key: str) -> str:
    e = _BY_KEY.get(key)
    if not e:
        return ""
    if e["kind"] == "script":
        if e["attr"] not in _SCRIPT_DEFAULTS:
            _snap(e["attr"])
        return _SCRIPT_DEFAULTS.get(e["attr"], "")
    if e["kind"] == "page":
        idx = e["index"]
        return _HELP_PAGES_DEFAULTS[idx] if idx < len(_HELP_PAGES_DEFAULTS) else ""
    if e["kind"] == "module":
        if e["attr"] == "CUSTOM_FILE_CAPTION":
            return _DEFAULT_CUSTOM_FILE_CAPTION
        if e["attr"] == "IMDB_TEMPLATE":
            return _DEFAULT_IMDB_TEMPLATE
    if e["kind"] == "runtime":
        return RUNTIME_DEFAULTS.get(key, "")
    return ""


def apply_value(key: str, value: str) -> None:
    """Push `value` live, instantly, with no restart required."""
    e = _BY_KEY.get(key)
    if not e:
        return
    if e["kind"] == "script":
        if e["attr"] not in _SCRIPT_DEFAULTS:
            _snap(e["attr"])
        setattr(script, e["attr"], value)
    elif e["kind"] == "page":
        pages = list(getattr(script, "HELP_PAGES", []))
        idx = e["index"]
        while len(pages) <= idx:
            pages.append("")
        pages[idx] = value
        script.HELP_PAGES = pages
    elif e["kind"] == "module":
        for mod in _module_targets(e["attr"]):
            setattr(mod, e["attr"], value)
    elif e["kind"] == "runtime":
        RUNTIME_LIVE[key] = value


async def save_text(key: str, value: str) -> None:
    """Persist + apply instantly."""
    apply_value(key, value)
    await texts_db.set(key, value)


async def reset_text(key: str) -> None:
    """Revert to hardcoded default, persist the reset, apply instantly."""
    apply_value(key, get_default(key))
    await texts_db.reset(key)


async def load_all_from_db() -> int:
    """Call once at bot startup, after DB connects. Applies every saved
    override so live behaviour matches the last saved state. Returns the
    number of overrides applied."""
    try:
        overrides = await texts_db.get_all()
    except Exception as e:
        logger.exception("text_registry: failed loading overrides: %s", e)
        return 0
    count = 0
    for key, value in overrides.items():
        if key in _BY_KEY:
            apply_value(key, value)
            count += 1
    return count
