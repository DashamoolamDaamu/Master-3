from kurigram import Client, filters
from utils import temp
from kurigram.types import Message
from database.users_chats_db import db
from kurigram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import SUPPORT_CHAT
import text_registry

async def banned_users(_, client, message: Message):
    return (
        message.from_user is not None or not message.sender_chat
    ) and message.from_user.id in temp.BANNED_USERS

banned_user = filters.create(banned_users)

async def disabled_chat(_, client, message: Message):
    return message.chat.id in temp.BANNED_CHATS

disabled_group=filters.create(disabled_chat)


@Client.on_message(filters.private & banned_user & filters.incoming)
async def ban_reply(bot, message):
    ban = await db.get_ban_status(message.from_user.id)
    try:
        text = text_registry.get_live_text("ban_message").format(reason=ban["ban_reason"])
    except Exception:
        text = text_registry.RUNTIME_DEFAULTS["ban_message"].format(reason=ban["ban_reason"])
    await message.reply(text)

@Client.on_message(filters.group & disabled_group & filters.incoming)
async def grp_bd(bot, message):
    buttons = [[
        InlineKeyboardButton('𝚂𝚞𝚙𝚙𝚘𝚛𝚝', url=f'https://t.me/mnbots_support')
    ]]
    reply_markup=InlineKeyboardMarkup(buttons)
    vazha = await db.get_chat(message.chat.id)
    try:
        text = text_registry.get_live_text("disabled_chat_message").format(reason=vazha['reason'])
    except Exception:
        text = text_registry.RUNTIME_DEFAULTS["disabled_chat_message"].format(reason=vazha['reason'])
    k = await message.reply(
        text=text,
        reply_markup=reply_markup)
    try:
        await k.pin()
    except:
        pass
    await bot.leave_chat(message.chat.id)
