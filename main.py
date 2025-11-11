import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from zoneinfo import ZoneInfo  # ✅ pytz o‘rniga tavsiya etiladi

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

# 🔑 Bot token
BOT_TOKEN = "8225995763:AAECJLO4W6Mv_Z7Kb5jY6hDmYOJKgBqQzZo"

# 👑 Super-admin (faqat reset huquqi bor)
SUPER_ADMIN_ID = 2034173364

# 👥 Adminlar
ADMINS = [
    1369536792, # 1-admin 
    95359885, # 2-admin 
    6396756710, # 3-admin 
    5767375856, # 4-admin 
    1377825742, # 5-admin 
    6596562858, # 6-admin 
    6842211104, # 7-admin 
    3603353, # 8-admin 
    928486130, # 9-admin 
    851275384, # 10-admin 
    50709839, # 11-admin 
    80594222, # 12-admin 
    5101023649, # 13-admin
    335509024, # 14-admin
    7944634580, # 14-admin
    2034173364, # 15-admin (To‘lqinjon Naimov) 
]

# Admin ismlari
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

# 🚚 Kuryerlar
COURIERS = {
    "Abdunazarov Akmaljon": 6393157349,
    "Азиз Файзуллаев": 7635875293,
    "Tulqinjon Naimov": 7084948337,
}

# Global
active_orders = {}     # {courier_id: [order_text1, order_text2, ...]}
order_history = []     # [(courier_name, order_text, start_time, end_time)]
pending_orders = []    # [(admin_id, order_text)]

dp = Dispatcher()
router = Router()
dp.include_router(router)

# —— yordamchi funksiyalar ——
def get_courier_name_by_id(user_id: int) -> str | None:
    for name, cid in COURIERS.items():
        if cid == user_id:
            return name
    return None

def is_admin(user_id: int) -> bool:
    return (user_id in ADMINS) or (user_id == SUPER_ADMIN_ID)

# ▶ Start
@router.message(CommandStart())
async def start_handler(msg: Message):
    if is_admin(msg.from_user.id):
        await msg.answer("Xush kelibsiz Admin!\nBuyurtma ma'lumotlarini kiriting:")
    else:
        await msg.answer("Iltimos ismingiz va familiyangizni kiriting:")

# 📦 Buyurtma yoki kuryer login
@router.message(F.text & ~F.text.startswith("/"))
async def courier_auth(msg: Message):
    global pending_orders

    if msg.from_user.id in ADMINS:  # Admin buyurtma yaratadi
        order_text = msg.text.strip()
        if not order_text:
            await msg.answer("❗ Buyurtma matni bo'sh bo'lmasligi kerak.")
            return

                # ✅ Agar barcha kuryerlar band bo‘lsa
        all_couriers_busy = all(cid in active_orders and active_orders[cid] for cid in COURIERS.values())
        if all_couriers_busy:
            await msg.answer("🚫 Hozirda barcha kuryerlar band.\n"
                             "Sizning buyurtmangizni bo‘shagan kuryer bo‘shaganda qabul qiladi.")
            # Buyurtmani baribir pending_orders ro‘yxatiga qo‘shamiz
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
                    f"📦 Yangi buyurtma paydo bo‘ldi!\n👤 Admin: {admin_name}\n\n{order_text}",
                    reply_markup=kb.as_markup()
                )
            except Exception as e:
                logging.warning(f"Kuryerga yuborishda xatolik ({courier_name}): {e}")
        return

    # Kuryer login
    full_name = msg.text.strip()
    if full_name in COURIERS and msg.from_user.id == COURIERS[full_name]:
        await msg.answer("✅ Sizning shaxsingiz tasdiqlandi!\nBuyurtmalarni kuting.")
    elif full_name in COURIERS:
        await msg.answer("❌ Sizning Telegram ID mos kelmadi!")
    else:
        await msg.answer("❌ Bu ism familiya kuryerlar ro'yxatida yo‘q!")

# ✅ Qabul qilish
@router.callback_query(F.data == "accept")
async def accept_order(callback: CallbackQuery):
    global active_orders, pending_orders, order_history

    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if not courier_name:
        await callback.answer("❌ Siz kuryerlar ro'yxatida emassiz.", show_alert=True)
        return

    if not pending_orders:
        await callback.answer("❌ Hozir ochiq buyurtma yo'q.", show_alert=True)
        return

    # Eng birinchi buyurtmani olish
    admin_id, order_text = pending_orders.pop(0)
    active_orders.setdefault(courier_id, []).append(order_text)
    start_time = datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S")

    # ✅ order_history ga qo‘shish
    order_history.append((courier_name, order_text, start_time, None))

    # ✅ Faqat buyurtmani bergan admin'ga yuboriladi
    try:
        await callback.message.bot.send_message(
            admin_id,
            f"✅ Siz bergan buyurtma qabul qilindi!\n"
            f"👤 Kuryer: {courier_name}\n"
            f"📦 Buyurtma: {order_text}"
        )
    except Exception as e:
        logging.warning(f"Admin ({admin_id}) ga xabar yuborishda xato: {e}")

    kb = InlineKeyboardBuilder()
    kb.button(text="🏁 Buyurtmani yakunlash", callback_data="finish")
    await callback.message.answer("Siz buyurtmani qabul qildingiz, oq yo‘l!", reply_markup=kb.as_markup())
    await callback.answer()

# ❌ Rad etish
@router.callback_query(F.data == "reject")
async def reject_order(callback: CallbackQuery):
    await callback.message.answer("❌ Buyurtma rad etildi.")
    await callback.answer()

# 🏁 Yakunlash
@router.callback_query(F.data == "finish")
async def finish_order(callback: CallbackQuery):
    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if not courier_name:
        await callback.answer("❌ Siz kuryer emassiz.", show_alert=True)
        return

    if courier_id not in active_orders or not active_orders[courier_id]:
        await callback.answer("❌ Faol buyurtma yo‘q.", show_alert=True)
        return

    # Ro‘yxatdan birinchi buyurtmani olish
    order_text = active_orders[courier_id].pop(0)

    for i, (name, order, start, end) in enumerate(order_history):
        if name == courier_name and order == order_text and end is None:
            order_history[i] = (
                name,
                order,
                start,
                datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S")
            )
            break

        # ✅ Buyurtmani yaratgan adminni topamiz va unga xabar yuboramiz
    admin_id = None
    for a_id, order in pending_orders:
        if order == order_text:
            admin_id = a_id
            break
    if not admin_id:
        for (name, order, start, end) in order_history:
            if name == courier_name and order == order_text:
                for possible_admin in ADMINS:
                    try:
                        await callback.bot.send_message(
                            possible_admin,
                            f"📦 Siz yaratgan buyurtma yakunlandi!\n"
                            f"👤 Kuryer: {courier_name}\n"
                            f"🕒 Tugallangan: {datetime.now(uzb_tz).strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        break
                    except Exception:
                        continue
                break

    await callback.message.answer("🏁 Buyurtma yakunlandi.")
    await callback.answer()

# 📊 Hisobot
@router.message(Command("hisobot"))
async def reports(msg: Message):
    if not order_history:
        await msg.answer("📊 Hali hisobotlar yo‘q!")
        return

    text = "📊 Hisobotlar:\n\n"
    stats = {}
    for courier, order, start_time, end_time in order_history:
        if courier not in stats:
            stats[courier] = []
        stats[courier].append((order, start_time, end_time))

    for courier, orders in stats.items():
        done_count = sum(1 for _, _, end in orders if end)
        text += f"👤 {courier}\nYetkazgan buyurtmalar soni: {done_count}\n"
        for order, start_time, end_time in orders:
            if end_time:
                text += (
                    f"   • {order}\n"
                    f"     Boshlangan: {start_time}\n"
                    f"     Yakunlangan: {end_time}\n"
                )
            else:
                text += (
                    f"   • {order}\n"
                    f"     Boshlangan: {start_time}\n"
                    f"     Yakunlanmagan ❌\n"
                )
        text += "\n"

    await msg.answer(text)

# 🆕 Reset
@router.message(Command("reset_hisobot"))
async def reset_reports(msg: Message):
    global order_history, active_orders, pending_orders
    if msg.from_user.id != SUPER_ADMIN_ID:
        await msg.answer("❌ Sizda huquq yo‘q!")
        return

    order_history = []
    active_orders = {}
    pending_orders = []
    await msg.answer("✅ Hisobotlar 0 dan boshlandi!")

# 📤 Excel eksport
@router.message(Command("export_hisobot"))
async def export_reports(msg: Message):
    if not OPENPYXL_AVAILABLE:
        await msg.answer("❌ Excel uchun 'openpyxl' yo‘q.\n"
                         "O‘rnating: pip install openpyxl")
        return

    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Sizda huquq yo‘q!")
        return

    if not order_history:
        await msg.answer("📊 Hisobotlar yo‘q!")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hisobot"
    ws.append(["Kuryer", "Buyurtma", "Boshlanish", "Tugash"])

    for courier, order, start_time, end_time in order_history:
        ws.append([courier, order, start_time, end_time or "❌ Yakunlanmagan"])

    file_path = "hisobot.xlsx"
    wb.save(file_path)

    file = FSInputFile(file_path)
    await msg.answer_document(file, caption="📊 Hisobot fayli!")

# ▶ Main
async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # ❗ Webhookni o‘chirib tashlash
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





