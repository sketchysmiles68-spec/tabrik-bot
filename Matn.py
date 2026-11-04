import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# BotFather'дан олган токенингиз
TOKEN = "9297193281:AAHSqFNe5uychiNkrX0xtUsRrpI2NblW0jw"

# Оз Telegram ID рақамингиз (@userinfobot орқали олинган)
ADMIN_ID = 7278107089  # <--- Шу ерга ўз ID'ингизни ёзинг

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

user_languages = {}
user_orders = {}
used_receipts = set()  # Чекларни қайта ишлатилмаслиги учун хотира


# --- Buyurtma bosqichlari (FSM) ---
class OrderState(StatesGroup):
  waiting_for_service_type = State()  # Хизмат турини танлаш
  waiting_for_recipient = State()  # Кимга аталгани
  waiting_for_contact = State()  # Табрикланувчининг Telegram ID / username
  waiting_for_datetime = State()  # Вақти
  waiting_for_text = State()  # Матн
  waiting_for_receipt = State()  # Тўлов чеки


# --- Қисқа матнларни бойитиш (AI мантиғи) ---
def expand_greeting_text(short_text: str) -> str:
  text_clean = short_text.strip().capitalize()

  # Агар матн жуда қисқа бўлса, уни байрамона кўринишга келтирамиз
  if len(text_clean.split()) <= 4:
    expanded = (
        f"🎉 **Муборак бўлсин!**\n\n"
        f"Чин қалбимдан тилайманки, ушбу қутлуғ айём сизга мустаҳкам соғлиқ, "
        f"оилавий хотиржамлик ва чексиз қувонч олиб келсин! Ҳамиша юзингиздан табассум аримасин!\n\n"
        f"💬 *Аслида юборилган қисқа тилак:* \"{text_clean}\""
    )
    return expanded
  return text_clean


TEXTS = {
    "uz_lat": {
        "main_menu": (
            "Asosiy menyu:\n"
            "Xizmat turlari va narxlari:\n"
            "📝 Matnli tabrik: 10 000 so'm\n"
            "🎙 Ovozli (audio) tabrik: 20 000 so'm\n"
            "🎬 Video tabrik: 30 000 so'm\n\n"
            "Davom etish uchun quyidagilardan birini tanlang:"
        ),
        "btn_order": "🎁 Tabrik buyurtma qilish",
        "btn_my_orders": "📦 Mening buyurtmalarim",
        "btn_support": "📞 Aloqa va yordam",
        "choose_service": "Iltimos, tabrik turini tanlang:",
        "srv_text": "📝 Matnli tabrik (10 000 so'm)",
        "srv_audio": "🎙 Ovozli tabrik (20 000 so'm)",
        "srv_video": "🎬 Video tabrik (30 000 so'm)",
        "ask_recipient": (
            "Iltimos, tabrik **kimga** mo'ljallanganini yozing (Masalan:"
            " *Akamga*):"
        ),
        "ask_contact": (
            "⚠️ **MUHIM OGOHLANTIRISH:**\n"
            "Tabrik belgilangan vaqtda avtomatik yetkazilishi uchun"
            " **tabriklanuvchi ham ushbu botga kirib /start tugmasini"
            " bosgan bo'lishi kerak!**\n\n"
            "Iltimos, tabriklanuvchining Telegram username'ini (@username) yoki"
            " ID raqamini kiriting:"
        ),
        "ask_datetime": (
            "Tabrik qaysi vaqtda yuborilishi kerak?\n"
            "Iltimos, yil, oy, kun va soatni kiriting (Masalan: *2026-yil"
            " 15-noyabr, soat 14:30*):"
        ),
        "ask_text": (
            "Ajoyib! Endi tabrik matnini yozib yuboring (qisqa yozsangiz ham"
            " bot uni chiroyli kengaytirib beradi):"
        ),
        "ask_receipt": (
            "💳 **To'lov jarayoni:**\n\n"
            "Siz tanlagan xizmat narxi: **{price} so'm**\n"
            "Iltimos, ushbu summani quyidagi karta raqamiga o'tkazing:\n"
            "`9860 1801 0530 8803`\n\n"
            "Pul o'tkazilgach, to'lov **chekining rasmini (skrinshotini)** shu"
            " yerga yuboring:"
        ),
        "success": (
            "✅ **Buyurtmangiz va to'lov chekingiz qabul qilindi!**\n\n"
            "Adminlarimiz tekshirib, belgilangan vaqtda tabriklanuvchiga"
            " yetkazishadi."
        ),
        "duplicate_receipt": (
            "⚠️ **Diqqat!** Bu chek ilgari ishlatilgan! Iltimos, yangi to'lov"
            " chekining rasmini yuboring."
        ),
        "no_orders": "Sizda hozircha faol buyurtmalar yo'q.",
        "support_text": (
            "📞 **Bog'lanish uchun:**\nSavollar bo'yicha adminlarimizga yozing:"
            " @SizningAdminUsernamengiz"
        ),
    },
    "uz_cyr": {
        "main_menu": (
            "Асосий меню:\n"
            "Хизмат турлари ва нархлари:\n"
            "📝 Матнли табрик: 10 000 сўм\n"
            "🎙 Овозли (аудио) табрик: 20 000 сўм\n"
            "🎬 Видео табрик: 30 000 сўм\n\n"
            "Давом этиш учун қуйидагилардан бирини танланг:"
        ),
        "btn_order": "🎁 Табрик буюртма қилиш",
        "btn_my_orders": "📦 Менинг буюртмаларим",
        "btn_support": "📞 Алоқа ва ёрдам",
        "choose_service": "Илтимос, табрик турини танланг:",
        "srv_text": "📝 Матнли табрик (10 000 сўм)",
        "srv_audio": "🎙 Овозли табрик (20 000 сўм)",
        "srv_video": "🎬 Видео табрик (30 000 сўм)",
        "ask_recipient": (
            "Илтимос, табрик **кимга** мўлжалланганини ёзинг (Масалан:"
            " *Акамга*):"
        ),
        "ask_contact": (
            "⚠️ **МУҲИМ ОГОҲЛАНТИРИШ:**\n"
            "Табрик белгиланган вақтда автоматик етказилиши учун"
            " **табрикланувчи ҳам ушбу ботга кириб /start тугмасини"
            " босган бўлиши керак!**\n\n"
            "Илтимос, табрикланувчининг Телеграм username'ини (@username) ёки"
            " ID рақамини киритинг:"
        ),
        "ask_datetime": (
            "Табрик қайси вақтда юборилиши керак?\n"
            "Илтимос, йил, ой, кун ва соатни киритинг (Масалан: *2026-йил"
            " 15-ноябр, соат 14:30*):"
        ),
        "ask_text": (
            "Ажойиб! Энди табрик матнини ёзиб юборинг (қисқа ёзсангиз ҳам бот"
            " уни чиройли кенгайтириб беради):"
        ),
        "ask_receipt": (
            "💳 **Тўлов жараёни:**\n\n"
            "Сиз танлаган хизмат нархи: **{price} сўм**\n"
            "Илтимос, ушбу суммани қуйидаги карта рақамига ўтказинг:\n"
            "`9860 1801 0530 8803`\n\n"
            "Пул ўтказилгач, тўлов **чекининг расмини (скриншотини)** шу ерга"
            " юборинг:"
        ),
        "success": (
            "✅ **Буюртмангиз ва тўлов чекингиз қабул қилинди!**\n\n"
            "Админларимиз текшириб, белгиланган вақтда табрикланувчига"
            " етказишади."
        ),
        "duplicate_receipt": (
            "⚠️ **Диққат!** Бу чек илгари ишлатилган! Илтимос, янги тўлов"
            " чекининг расмини юборинг."
        ),
        "no_orders": "Сизда ҳозирда фаол буюртмалар йўқ.",
        "support_text": (
            "📞 **Боғланиш учун:**\nСаволлар бўйича админларимизга ёзинг:"
            " @SizningAdminUsernamengiz"
        ),
    },
}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
  await state.clear()
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="Latinscha 🇺🇿", callback_data="uz_lat"),
              InlineKeyboardButton(text="Kirillcha 🇺🇿", callback_data="uz_cyr"),
          ]
      ]
  )
  await message.answer(
      "Assalomu alaykum! Hurmatli foydalanuvchi, alifboni tanlang:\n"
      "Здравствуйте! Пожалуйста, выберите алфавит:",
      reply_markup=keyboard,
  )


@router.callback_query(F.data.in_(["uz_lat", "uz_cyr"]))
async def set_language(callback: CallbackQuery, state: FSMContext):
  await state.clear()
  full_lang = callback.data
  user_languages[callback.from_user.id] = full_lang
  t = TEXTS[full_lang]

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text=t["btn_order"], callback_data="order_start")],
          [
              InlineKeyboardButton(
                  text=t["btn_my_orders"], callback_data="my_orders"
              )
          ],
          [InlineKeyboardButton(text=t["btn_support"], callback_data="support")],
      ]
  )

  await callback.message.edit_text(t["main_menu"], reply_markup=keyboard)
  await callback.answer()


# --- BUYURTMA BOSHLANISHI VA XIZMAT TURINGI TANLASH ---
@router.callback_query(F.data == "order_start")
async def start_order(callback: CallbackQuery, state: FSMContext):
  lang = user_languages.get(callback.from_user.id, "uz_lat")
  t = TEXTS[lang]

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text=t["srv_text"], callback_data="srv_10000"
              )
          ],
          [
              InlineKeyboardButton(
                  text=t["srv_audio"], callback_data="srv_20000"
              )
          ],
          [
              InlineKeyboardButton(
                  text=t["srv_video"], callback_data="srv_30000"
              )
          ],
      ]
  )

  await callback.message.answer(t["choose_service"], reply_markup=keyboard)
  await state.set_state(OrderState.waiting_for_service_type)
  await callback.answer()


@router.callback_query(
    OrderState.waiting_for_service_type, F.data.startswith("srv_")
)
async def process_service_type(callback: CallbackQuery, state: FSMContext):
  price_map = {
      "srv_10000": ("Matnli tabrik", "10 000"),
      "srv_20000": ("Ovozli tabrik", "20 000"),
      "srv_30000": ("Video tabrik", "30 000"),
  }
  srv_title, price = price_map.get(callback.data, ("Matnli tabrik", "10 000"))

  await state.update_data(service_name=srv_title, price=price)
  lang = user_languages.get(callback.from_user.id, "uz_lat")
  t = TEXTS[lang]

  await callback.message.answer(t["ask_recipient"])
  await state.set_state(OrderState.waiting_for_recipient)
  await callback.answer()


@router.message(OrderState.waiting_for_recipient)
async def process_recipient(message: Message, state: FSMContext):
  await state.update_data(recipient=message.text.strip().capitalize())
  lang = user_languages.get(message.from_user.id, "uz_lat")
  t = TEXTS[lang]

  await message.answer(t["ask_contact"], parse_mode="Markdown")
  await state.set_state(OrderState.waiting_for_contact)


@router.message(OrderState.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext):
  await state.update_data(contact=message.text.strip())
  lang = user_languages.get(message.from_user.id, "uz_lat")
  t = TEXTS[lang]

  await message.answer(t["ask_datetime"])
  await state.set_state(OrderState.waiting_for_datetime)


@router.message(OrderState.waiting_for_datetime)
async def process_datetime(message: Message, state: FSMContext):
  await state.update_data(datetime=message.text.strip())
  lang = user_languages.get(message.from_user.id, "uz_lat")
  t = TEXTS[lang]

  await message.answer(t["ask_text"])
  await state.set_state(OrderState.waiting_for_text)


@router.message(OrderState.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
  # Matnni kengaytirish / AI mantiqiy ishlovi
  expanded_text = expand_greeting_text(message.text)
  await state.update_data(greeting_text=expanded_text)

  data = await state.get_data()
  price = data.get("price", "10 000")

  lang = user_languages.get(message.from_user.id, "uz_lat")
  t = TEXTS[lang]

  await message.answer(
      t["ask_receipt"].format(price=price), parse_mode="Markdown"
  )
  await state.set_state(OrderState.waiting_for_receipt)


@router.message(OrderState.waiting_for_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  lang = user_languages.get(message.from_user.id, "uz_lat")
  t = TEXTS[lang]

  # Takroriy chekni bloklash
  if photo_id in used_receipts:
    await message.answer(t["duplicate_receipt"])
    return

  used_receipts.add(photo_id)

  data = await state.get_data()
  srv_name = data.get("service_name")
  price = data.get("price")
  recipient = data.get("recipient")
  contact = data.get("contact")
  datetime_str = data.get("datetime")
  greeting_text = data.get("greeting_text")

  user_orders[message.from_user.id] = {
      "recipient": recipient,
      "datetime": datetime_str,
      "service": srv_name,
  }

  await message.answer(t["success"])

  # Adminga yuborish
  try:
    username_info = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Yo'q"
    )
    admin_caption = (
        f"🔔 **Yangi Tasdiqlangan Buyurtma!**\n\n"
        f"📦 **Xizmat turi:** {srv_name} ({price} so'm)\n"
        f"👤 **Buyurtmachi:** {message.from_user.full_name} ({username_info})\n"
        f"🆔 **ID:** `{message.from_user.id}`\n"
        f"🎯 **Kimga:** {recipient}\n"
        f"📱 **Qabul qiluvchi manzili:** {contact}\n"
        f"⏰ **Belgilangan vaqt:** {datetime_str}\n\n"
        f"📝 **Кенгайтирилган Табрик матни:**\n{greeting_text}"
    )
    await bot.send_photo(
        ADMIN_ID, photo=photo_id, caption=admin_caption, parse_mode="Markdown"
    )
  except Exception as e:
    logging.error(f"Adminga yuborishda xatolik: {e}")

  await state.clear()


@router.message(OrderState.waiting_for_receipt)
async def wrong_receipt(message: Message):
  lang = user_languages.get(message.from_user.id, "uz_lat")
  text = (
      "Iltimos, matn yozmang, to'lov chekining **rasmini (skrinshotini)**"
      " yuboring!"
      if lang == "uz_lat"
      else "Илтимос, матн ёзманг, тўлов чекининг **расмини (скриншотини)**"
      " юборинг!"
  )
  await message.answer(text)


@router.callback_query(F.data == "my_orders")
async def my_orders_handler(callback: CallbackQuery):
  lang = user_languages.get(callback.from_user.id, "uz_lat")
  t = TEXTS[lang]
  order = user_orders.get(callback.from_user.id)

  if order:
    text = (
        f"📦 **Sizning oxirgi buyurtmangiz:**\n\n"
        f"📌 Xizmat: {order['service']}\n"
        f"🎯 Kimga: {order['recipient']}\n"
        f"⏰ Vaqti: {order['datetime']}\n"
        f"🟢 Holati: Qabul qilingan va navbatga qo'yilgan"
        if lang == "uz_lat"
        else f"📦 **Сизнинг охирги буюртмангиз:**\n\n"
        f"📌 Хизмат: {order['service']}\n"
        f"🎯 Кимга: {order['recipient']}\n"
        f"⏰ Вақти: {order['datetime']}\n"
        f"🟢 Ҳолати: Қабул қилинган ва навбатга қўйилган"
    )
  else:
    text = t["no_orders"]

  await callback.answer()
  await callback.message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
  lang = user_languages.get(callback.from_user.id, "uz_lat")
  t = TEXTS[lang]
  await callback.answer()
  await callback.message.answer(t["support_text"], parse_mode="Markdown")


async def main():
  dp.include_router(router)
  print("Bot muvaffaqiyatli ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())