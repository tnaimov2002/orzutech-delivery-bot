import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from zoneinfo import ZoneInfo

uzb_tz = ZoneInfo("Asia/Tashkent")

import logging
import pytz
uzb_tz = pytz.timezone("Asia/Tashkent")

from datetime import datetime


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
    1369536792,  # 1-admin
    95359885,    # 2-admin
    6396756710,  # 3-admin
    5767375856,  # 4-admin
    1377825742,  # 5-admin
    6596562858,  # 6-admin
    6842211104,  # 7-admin
    3603353,     # 8-admin
    928486130,   # 9-admin
    851275384,   # 10-admin
    50709839,    # 11-admin
    80594222,    # 12-admin
    2034173364,  # 13-admin (To‘lqinjon Naimov)
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
    2034173364: "To'lqinjon Naimov",
}

# 🚚 Kuryerlar ro‘yxati (ism familiya: Telegram ID)
COURIERS = {
    "Abdunazarov Akmaljon": 6393157349,
    "Mansur Maxmudov": 5277699739,
    "Tulqinjon Naimov": 7084948337,
}

# Global ma'lumotlar
active_orders = {}   # {courier_id: order_text}
order_history = []   # [(courier_name, order_text, start_time, end_time)]
pending_order = None # (admin_id, order_text)

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

# ▶ Start komandasi
@router.message(CommandStart())
async def start_handler(msg: Message):
    if is_admin(msg.from_user.id):
        await msg.answer("Xush kelibsiz Admin!\nBuyurtma ma'lumotlarini kiriting:")
    else:
        await msg.answer("Iltimos ismingiz va familiyangizni kiriting:")

# 📦 Admin buyurtma yaratadi yoki kuryer identifikatsiya qiladi
@router.message(F.text & ~F.text.startswith("/"))
async def courier_auth(msg: Message):
    global pending_order

    # Agar admin bo'lsa — buyurtma kiritadi
    if msg.from_user.id in ADMINS:
        order_text = msg.text.strip()
        if not order_text:
            await msg.answer("❗ Buyurtma matni bo'sh bo'lmasligi kerak.")
            return

        pending_order = (msg.from_user.id, order_text)
        await msg.answer("✅ Buyurtma yaratildi!")

        # Barcha kuryerlarga yuborish (faol bo'lmaganlarga)
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Qabul qilish", callback_data="accept")
        kb.button(text="❌ Rad etish", callback_data="reject")
        kb.adjust(2)

        admin_name = ADMIN_NAMES.get(msg.from_user.id, "Noma'lum admin")

        for courier_name, courier_id in COURIERS.items():
            if courier_id not in active_orders:
                try:
                    await msg.bot.send_message(
                        courier_id,
                        f"📦 Yangi buyurtma paydo bo‘ldi!\n👤 Admin: {admin_name}\n\n{order_text}",
                        reply_markup=kb.as_markup()
                    )
                except Exception as e:
                    logging.warning(f"Kuryerga yuborishda xatolik ({courier_name}): {e}")
        return

    # Oddiy foydalanuvchi (kuryer) ism familiya orqali kiradi
    full_name = msg.text.strip()
    if full_name in COURIERS and msg.from_user.id == COURIERS[full_name]:
        await msg.answer("✅ Sizning shaxsingiz tasdiqlandi!\nBuyurtmalarni kuting.")
    elif full_name in COURIERS:
        await msg.answer("❌ Sizning Telegram ID mos kelmadi!")
    else:
        await msg.answer("❌ Bu ism familiya kuryerlar ro'yxatida yo‘q!")

# ✅ Buyurtma qabul qilish (faqat buyurtmani bergan admin'ga xabar yuboriladi)
@router.callback_query(F.data == "accept")
async def accept_order(callback: CallbackQuery):
    global active_orders, pending_order

    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if not courier_name:
        await callback.answer("❌ Siz kuryerlar ro'yxatida emassiz.", show_alert=True)
        return

    if courier_id in active_orders:
        await callback.answer("❌ Sizda faol buyurtma bor. Avval yakunlang!", show_alert=True)
        return

    if not pending_order:
        await callback.answer("❌ Hozir qabul qilish uchun ochiq buyurtma yo'q.", show_alert=True)
        return

    # faqat bitta admin
    admin_id, order_text = pending_order
    active_orders[courier_id] = order_text
    start_time = datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S")
    order_history[i] = (name, order, start, datetime.now(uzb_tz).strftime("%Y-%m-%d %H:%M:%S"))

    # ✅ faqat buyurtmani bergan admin'ga yuboriladi
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

    pending_order = None

# ❌ Buyurtma rad etish
@router.callback_query(F.data == "reject")
async def reject_order(callback: CallbackQuery):
    await callback.message.answer("❌ Buyurtma rad etildi. Buyurtma boshqa kuryerlar uchun ochiq.")
    await callback.answer()

# 🏁 Buyurtmani yakunlash
@router.callback_query(F.data == "finish")
async def finish_order(callback: CallbackQuery):
    courier_id = callback.from_user.id
    courier_name = get_courier_name_by_id(courier_id)

    if not courier_name:
        await callback.answer("❌ Siz kuryerlar ro'yxatida emassiz.", show_alert=True)
        return

    if courier_id not in active_orders:
        await callback.answer("❌ Sizda yakunlash uchun faol buyurtma yo‘q.", show_alert=True)
        return

    order_text = active_orders[courier_id]

    for i, (name, order, start, end) in enumerate(order_history):
        if name == courier_name and order == order_text and end is None:
            order_history[i] = (name, order, start, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            break

    del active_orders[courier_id]
    await callback.message.answer("🏁 Buyurtma yakunlandi. Rahmat!")
    await callback.answer()

# 📊 Hisobot
@router.message(Command("hisobot"))
async def reports(msg: Message):
    if not order_history:
        await msg.answer("📊 Hali hisobotlar mavjud emas!")
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
                text += f"   • {order}\n     Boshlangan: {start_time}\n     Yakunlangan: {end_time}\n"
            else:
                text += f"   • {order}\n     Boshlangan: {start_time}\n     Yakunlanmagan ❌\n"
        text += "\n"

    await msg.answer(text)

# 🆕 Hisobotni 0 dan tashlash (faqat SUPER_ADMIN)
@router.message(Command("reset_hisobot"))
async def reset_reports(msg: Message):
    global order_history, active_orders, pending_order
    if msg.from_user.id != SUPER_ADMIN_ID:
        await msg.answer("❌ Sizda bu amalni bajarish huquqi yo‘q!")
        return

    order_history = []
    active_orders = {}
    pending_order = None
    await msg.answer("✅ Hisobotlar 0 dan qayta boshlandi!")

# 📤 Hisobotni Excel faylga eksport (adminlar yoki super-admin)
@router.message(Command("export_hisobot"))
async def export_reports(msg: Message):
    if not OPENPYXL_AVAILABLE:
        await msg.answer("❌ Excel eksport uchun 'openpyxl' o‘rnatilmagan.\n"
                         "Terminalda o‘rnating: pip install openpyxl")
        return

    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Sizda bu amalni bajarish huquqi yo‘q!")
        return

    if not order_history:
        await msg.answer("📊 Hali hisobotlar mavjud emas!")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hisobot"
    ws.append(["Kuryer", "Buyurtma", "Boshlanish vaqti", "Tugash vaqti"])

    for courier, order, start_time, end_time in order_history:
        ws.append([courier, order, start_time, end_time or "❌ Yakunlanmagan"])

    file_path = "hisobot.xlsx"
    wb.save(file_path)

    file = FSInputFile(file_path)
    await msg.answer_document(file, caption="📊 Hisobot fayli tayyor!")

# ▶ Main
async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



