import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

# O‘zbekiston vaqti
uzb_tz = ZoneInfo("Asia/Tashkent")

# Excel eksport uchun
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except Exception:
    OPENPYXL_AVAILABLE = False

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8225995763:AAG7rRptYFDMcY-U8D_cB5FO9-vW7oQBHOM"
SUPER_ADMIN_ID = 2034173364

ADMINS = [
    1369536792, 95359885, 6396756710, 5767375856, 1377825742,
    6596562858, 6842211104, 3603353, 928486130, 851275384,
    50709839, 80594222, 5101023649, 335509024, 7944634580,
    2034173364
]

ADMIN_NAMES = {
    1369536792: "Sulaymonov Shaxzod",
    95359885: "Usmanov Mirfayz",
    6396756710: "Muhammad Yormuxammedov",
    5767375856: "Mirali Berdiyev Nurmuhammadov",
    1377825742: "Chilmatov Sherzod",
    6596562858: "Shomurodov Shamshod",
    6842211104: "Sobir Abdullayev",
    3603353: "Salixov Islombek",
    928486130: "Xatamov Sanjar",
    851275384: "Nuritdinov Rustambek",
    50709839: "Akramov Shakhob",
    80594222: "Sobirov Umarbek",
    5101023649: "Sabirov Sharif",
    335509024: "Aripov Rajab",
    2034173364: "To'lqinjon Naimov",
}

COURIERS = {
    "Abdunazarov Akmaljon": 6393157349,
    "Азиз Файзуллаев": 7635875293,
    "Tulqinjon Naimov": 7084948337,
}

active_orders = {}
order_history = []
pending_orders = []

dp = Dispatcher()
router = Router()
dp.include_router(router)

def get_courier_name_by_id(user_id: int):
    for name, cid in COURIERS.items():
        if cid == user_id:
            return name
    return None

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS or user_id == SUPER_ADMIN_ID

@router.message(CommandStart())
async def start_handler(msg: Message):
    if is_admin(msg.from_user.id):
        await msg.answer("Xush kelibsiz Admin!\nBuyurtma ma'lumotlarini kiriting:")
    else:
        await msg.answer("Iltimos ismingiz va familiyangizni kiriting:")

@router.message(F.text & ~F.text.startswith("/"))
async def courier_auth(msg: Message):
    global pending_orders

    if msg.from_user.id in ADMINS:
        order_text = msg.text.strip()
        if not order_text:
            await msg.answer("❗ Buyurtma matni bo'sh bo'lmasligi kerak.")
            return

        all_couriers_busy = all(
            cid in active_orders and active_orders[cid]
            for cid in COURIERS.values()
        )
        if all_couriers_busy:
            await msg.answer("🚫 Hozirda barcha kuryerlar band.")
            pending_orders.append((msg.from_user.id, order_text))
            return

        pending_orders.append((msg.from_user.id, order_text))
        await msg.answer("✅ Buyurtma yaratildi!")

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Qabul qilish", callback_data="accept")
        kb.button(text="❌ Rad etish", callback_data="reject")
        kb.adjust(2)

        admin_name = ADMIN_NAMES.get(msg.from_user.id, "Noma'lum admin")

        for courier_name, courier_id in COURIERS.items():
            try:
                await msg.bot.send_message(
                    courier_id,
                    f"📦 Yangi buyurtma!\n👤 Admin: {admin_name}\n\n{order_text}",
                    reply_markup=kb.as_markup()
                )
                await asyncio.sleep(0.6)  # ✅ LIMIT FIX
            except Exception as e:
                logging.warning(f"Kuryerga yuborishda xato ({courier_name}): {e}")
                await asyncio.sleep(1.5)
        return

    full_name = msg.text.strip()
    if full_name in COURIERS and msg.from_user.id == COURIERS[full_name]:
        await msg.answer("✅ Sizning shaxsingiz tasdiqlandi!")
    elif full_name in COURIERS:
        await msg.answer("❌ Telegram ID mos kelmadi!")
    else:
        await msg.answer("❌ Bu ism ro'yxatda yo‘q!")

@router.callback_query(F.data == "accept")
async def accept_order(callback: CallbackQuery):
    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if not courier_name or not pending_orders:
        await callback.answer("❌ Buyurtma yo‘q", show_alert=True)
        return

    admin_id, order_text = pending_orders.pop(0)
    active_orders.setdefault(courier_id, []).append(order_text)

    start_time = datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S")
    order_history.append((courier_name, order_text, start_time, None))

    try:
        await callback.bot.send_message(
            admin_id,
            f"✅ Buyurtma qabul qilindi!\n👤 Kuryer: {courier_name}\n📦 {order_text}"
        )
        await asyncio.sleep(0.3)  # ✅ LIMIT FIX
    except Exception as e:
        logging.warning(e)

    kb = InlineKeyboardBuilder()
    kb.button(text="🏁 Buyurtmani yakunlash", callback_data="finish")
    await callback.message.answer("🚚 Buyurtmani qabul qildingiz!", reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data == "reject")
async def reject_order(callback: CallbackQuery):
    await callback.message.answer("❌ Buyurtma rad etildi.")
    await callback.answer()

@router.callback_query(F.data == "finish")
async def finish_order(callback: CallbackQuery):
    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if courier_id not in active_orders or not active_orders[courier_id]:
        await callback.answer("❌ Buyurtma yo‘q", show_alert=True)
        return

    order_text = active_orders[courier_id].pop(0)

    for i, (name, order, start, end) in enumerate(order_history):
        if name == courier_name and order == order_text and end is None:
            order_history[i] = (
                name, order, start,
                datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S")
            )
            break

    for admin_id in ADMINS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"📦 Buyurtma yakunlandi!\n👤 {courier_name}\n📦 {order_text}"
            )
            await asyncio.sleep(0.4)  # ✅ LIMIT FIX
            break
        except Exception:
            continue

    await callback.message.answer("🏁 Buyurtma yakunlandi.")
    await callback.answer()

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
# 🧹 Ushlanmagan xabarlar uchun (INFO logni yo‘qotish)
@router.message()
async def catch_all_messages(msg: Message):
    pass

if __name__ == "__main__":
    asyncio.run(main())


