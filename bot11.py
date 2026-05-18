import json
import os
import asyncio
import sqlite3
import gspread

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from google.oauth2.service_account import Credentials


scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


raw_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not raw_creds:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not set")

google_creds = json.loads(raw_creds)
google_creds["private_key"] = google_creds["private_key"].replace("\\n", "\n")


creds = Credentials.from_service_account_info(
    google_creds,
    scopes=scope
)
client = gspread.authorize(creds)
drive_service = build('drive', 'v3', credentials=creds)
TOKEN = "8678766563:AAHFf6TWhwGQD1zRQGmFAKnQF_sCWskp2oA"


bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
user_state = {}

conn = sqlite3.connect("bot_state.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_states (
    user_id INTEGER PRIMARY KEY,
    state TEXT,
    data TEXT
)
""")
conn.commit()


scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


FOLDER_ID = "12BfiTpeaBySVk1GmRzXZTZQwuqNMKIC_"
def save_user_state(user_id):
    cursor.execute("""
    INSERT OR REPLACE INTO user_states (user_id, state, data)
    VALUES (?, ?, ?)
    """, (
        user_id,
        user_state.get(user_id),
        json.dumps(user_data.get(user_id, {}), ensure_ascii=False)
    ))
    conn.commit()

def load_user_state(user_id):
    cursor.execute(
        "SELECT state, data FROM user_states WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if row:
        user_state[user_id] = row[0]
        user_data[user_id] = json.loads(row[1])
    else:
        user_state[user_id] = None
        user_data[user_id] = {}


def clear_user_state(user_id):
    cursor.execute(
        "DELETE FROM user_states WHERE user_id=?",
        (user_id,)
    )
    conn.commit()




def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Создать отчет")]],
        resize_keyboard=True
    )

def region_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Бишкек"), KeyboardButton(text="Ош")],
            [KeyboardButton(text="Чуй"), KeyboardButton(text="Ошская область")],
            [KeyboardButton(text="Иссык-Куль"), KeyboardButton(text="Нарын")],
            [KeyboardButton(text="Талас"), KeyboardButton(text="Баткен")]
        ],
        resize_keyboard=True
    )

def manager_menu():
    managers = [
        "Орозобаев А.К.", "Алымкулов А.Э.", "Качкынбаев М.А.",
        "Мусулумов Т.", "Чанаков Н.Д.", "Назиров И.",
        "Кокоев Н.", "Шабданов К.", "Бейшебаев Н.Д."
    ]

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=m)] for m in managers],
        resize_keyboard=True
    )


def confirm_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подтвердить"),
             KeyboardButton(text="Изменить")]
        ],
        resize_keyboard=True
    )

def edit_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ФИО"), KeyboardButton(text="Госномер")],
            [KeyboardButton(text="Литраж"), KeyboardButton(text="Цена")],
            [KeyboardButton(text="Пробег"), KeyboardButton(text="Регион")],
            [KeyboardButton(text="Фото"), KeyboardButton(text="Управляющий")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )

def upload_to_drive(file_path):
    print("НАЧАЛАСЬ ЗАГРУЗКА")
    print("ПУТЬ К ФАЙЛУ:", file_path)
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [FOLDER_ID]
    }
    print("МЕТАДАННЫЕ СОЗДАНЫ")

    media = MediaFileUpload(file_path, resumable=True)

    print("MEDIA СОЗДАН")

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id',
        supportsAllDrives=True
    ).execute()

    print("ФАЙЛ ЗАГРУЖЕН")

    file_id = file.get('id')

    print("ID ФАЙЛА:", file_id)

    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    print("ДОСТУП ВЫДАН")

    return f"https://drive.google.com/file/d/{file_id}/view"
    
def save_to_google(data):
    
    print("SAVE FUNCTION STARTED")

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    date_only = now.strftime("%Y-%m-%d")
    
    print('Открываю таблицу')

    try:
        spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1m7yTaIIn7IhnSBD8p35-Cz9NuoZmGs2jzVA8Js9kVdk/edit?usp=sharing")
        print('Таблица открыта')


    except Exception as e:
        print("OPEN ERROR:", repr(e))
        raise
    manager = data["manager"]  

    try:
        print('ИЩУУУУ')
        sheet = spreadsheet.worksheet(manager)
        print('НАШЕЕЕЛ')
    except Exception as e:
        print('Таблица ННАЙДЕНА')
        sheet = spreadsheet.add_worksheet(
            title=manager, rows="1000", cols="20")
        
        print('Страница создана')

        
        sheet.append_row([
            "name",
            "car",
            "liters",
            "price",
            "km",
            "region",
            "photo",
            "manager",
            "datetime",
            "sum",
            "km_today"
        ])
        print(' Загаловки дабавлены')

    
    photo_link = ""
    if data.get("photo"):
        photo_link = upload_to_drive(data["photo"])

    total = float(data["liters"]) * float(data["price"])


    sheet.append_row([
        data["name"],
        data["car"],
        data["liters"],
        data["price"],
        data["km"],
        data["region"],
        f'=HYPERLINK("{photo_link}", "Открыть фото")',
        manager,
        date_str,
        total,
        0
    ])


    try:
        summary = spreadsheet.worksheet("Summary")
    except:
        summary = spreadsheet.add_worksheet(title="Summary", rows="1000", cols="10")

        summary.append_row([
            "Дата",
            "Менеджер",
            "Литры"
        ])

    summary.append_row([
        date_only,
        manager,
        float(data["liters"])
    ])
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Выбери действие:",
        reply_markup=main_menu()
    )

@dp.message()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_state:
        load_user_state(user_id)

    if text == "Создать отчет":
        user_data[user_id] = {}
        user_state[user_id] = "name"
        save_user_state(user_id)
        await message.answer("Введи ФИО:")
        return

    elif user_state.get(user_id) == "name":
        user_data[user_id]["name"] = text
        user_state[user_id] = "car"
        save_user_state(user_id)
        await message.answer("Введи госномер:")
        return

    elif user_state.get(user_id) == "car":
        user_data[user_id]["car"] = text
        user_state[user_id] = "liters"
        save_user_state(user_id)
        await message.answer("Введи литраж:")
        return

    elif user_state.get(user_id) == "liters":
        user_data[user_id]["liters"] = float(text)
        user_state[user_id] = "price"
        save_user_state(user_id)
        await message.answer("Введи цену:")
        return

    elif user_state.get(user_id) == "price":
        user_data[user_id]["price"] = float(text)
        user_state[user_id] = "km"
        save_user_state(user_id)
        await message.answer("Введи пробег:")
        return

    elif user_state.get(user_id) == "km":
        user_data[user_id]["km"] = int(text)
        user_state[user_id] = "region"
        save_user_state(user_id)
        await message.answer("Выбери регион:", reply_markup=region_menu())
        return

    elif user_state.get(user_id) == "region":
        user_data[user_id]["region"] = text
        user_state[user_id] = "photo"
        save_user_state(user_id)
        await message.answer("Отправь фото:")
        return

    elif user_state.get(user_id) == "photo":
        if message.photo:
            photo = message.photo[-1]

            file_info = await bot.get_file(photo.file_id)
            downloaded = await bot.download_file(file_info.file_path)

            os.makedirs("temp", exist_ok=True)

            filename = f"temp/{user_id}_{datetime.now().timestamp()}.jpg"

            with open(filename, "wb") as f:
                f.write(downloaded.read())

            full_path = os.path.abspath(filename)
            user_data[user_id]["photo"] = full_path
            
            user_state[user_id] = "manager"
            save_user_state(user_id)

            await message.answer(
                "Выбери управляющего:",
                reply_markup=manager_menu()
            )
        else:
            await message.answer("Отправь фото.")
        return

    elif user_state.get(user_id) == "manager":
        user_data[user_id]["manager"] = text
        user_state[user_id] = "confirm"
        save_user_state(user_id)

        data = user_data[user_id]

        preview = (
            f"Проверь:\n\n"
            f"ФИО: {data['name']}\n"
            f"Госномер: {data['car']}\n"
            f"Литраж: {data['liters']}\n"
            f"Цена: {data['price']}\n"
            f"Сумма: {float(data['liters']) * float(data['price'])}\n"
            f"Пробег: {data['km']}\n"
            f"Регион: {data['region']}\n"
            f"Фото: {data.get('photo', 'Нет')}\n"
            f"Управляющий: {data['manager']}"
        )

        await message.answer(preview, reply_markup=confirm_menu())
        return
    else:
     print("CURRENT STATE:", user_state.get(user_id))
     print("USER TEXT:", text)

     if user_state.get(user_id) == "confirm":

        if text == "Подтвердить":
            print("CONFIRM BUTTON PRESSED")
            print("Начинаю запись в Google")

            try:
              print('Вызываю Гугл')
              await asyncio.to_thread(save_to_google, user_data[user_id])
              print('Выполнено')
             
              clear_user_state(user_id)
              user_state[user_id] = None
              user_data[user_id] = {}

              await message.answer(
                "Сохранено!",
                reply_markup=main_menu()
            )

            except Exception as e:
               print('ОШИБКА')
               await message.answer(f"Ошибка: {e}")

            return

        elif text == "Изменить":
            user_state[user_id] = "edit_select"
            save_user_state(user_id)

            await message.answer(
                "Выберите пункт",
                reply_markup=edit_menu()
            )
            return

     elif user_state.get(user_id) == "edit_select":

          if text == "Отмена":
           user_state[user_id] = "confirm"
           save_user_state(user_id)

           data = user_data[user_id]

           preview = (
            f"Проверь:\n\n"
            f"ФИО: {data['name']}\n"
            f"Госномер: {data['car']}\n"
            f"Литраж: {data['liters']}\n"
            f"Цена: {data['price']}\n"
            f"Сумма: {float(data['liters']) * float(data['price'])}\n"
            f"Пробег: {data['km']}\n"
            f"Регион: {data['region']}\n"
            f"Фото: {data.get('photo', 'Нет')}\n"
            f"Управляющий: {data['manager']}"
        )
           user_state[user_id] = "confirm"
           print("STATE SET TO CONFIRM")
           await message.answer(preview, reply_markup=confirm_menu())
           return

    fields = {
        "ФИО": "name",
        "Госномер": "car",
        "Литраж": "liters",
        "Цена": "price",
        "Пробег": "km",
        "Регион": "region",
        "Фото": "photo",
        "Управляющий": "manager"
    }

    if text in fields:
        field = fields[text]

    
        if field == "region":
            user_state[user_id] = "edit_region"
            save_user_state(user_id)
            await message.answer("Выбери регион:", reply_markup=region_menu())
            return

        elif field == "manager":
            user_state[user_id] = "edit_manager"
            save_user_state(user_id)
            await message.answer("Выбери управляющего:", reply_markup=manager_menu())
            return

        
        user_state[user_id] = f"edit_{field}"
        save_user_state(user_id)
        await message.answer("Введи новое значение:")
        return


    elif str(user_state.get(user_id)).startswith("edit_"):

       field = user_state[user_id].replace("edit_", "")


    if text == "Отмена":
        user_state[user_id] = "confirm"
        save_user_state(user_id)

        data = user_data[user_id]

        preview = (
            f"Проверь:\n\n"
            f"ФИО: {data['name']}\n"
            f"Госномер: {data['car']}\n"
            f"Литраж: {data['liters']}\n"
            f"Цена: {data['price']}\n"
            f"Сумма: {float(data['liters']) * float(data['price'])}\n"
            f"Пробег: {data['km']}\n"
            f"Регион: {data['region']}\n"
            f"Фото: {data.get('photo', 'Нет')}\n"
            f"Управляющий: {data['manager']}"
        )

        await message.answer(preview, reply_markup=confirm_menu())
        return

    if 'field' not in locals():
         return
    if field == "photo":
        if message.photo:
            photo = message.photo[-1]

            file_info = await bot.get_file(photo.file_id)
            downloaded = await bot.download_file(file_info.file_path)

            os.makedirs("temp", exist_ok=True)

            filename = f"temp/{user_id}_{datetime.now().timestamp()}.jpg"

            with open(filename, "wb") as f:
                f.write(downloaded.read())

            user_data[user_id]["photo"] = os.path.abspath(filename)
        else:
            await message.answer("Отправь фото.")
            return

    else:
        user_data[user_id][field] = text


    user_state[user_id] = "confirm"
    save_user_state(user_id)

    data = user_data[user_id]

    preview = (
        f"Проверь:\n\n"
        f"ФИО: {data['name']}\n"
        f"Госномер: {data['car']}\n"
        f"Литраж: {data['liters']}\n"
        f"Цена: {data['price']}\n"
        f"Сумма: {float(data['liters']) * float(data['price'])}\n"
        f"Пробег: {data['km']}\n"
        f"Регион: {data['region']}\n"
        f"Фото: {data.get('photo', 'Нет')}\n"
        f"Управляющий: {data['manager']}"
    )

    await message.answer(preview, reply_markup=confirm_menu())
async def main():
    print("Бот работает...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())