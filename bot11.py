import os
import asyncio
import json
import sqlite3
import gspread
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive']

creds = None

if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

drive_service = build('drive', 'v3', credentials=creds)
client = gspread.authorize(creds)

TOKEN = "8678766563:AAHop7Gh9MNA7OyrPxGQc-M0xut9OUDyg0k"


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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")


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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))



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
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [FOLDER_ID]
    }

    media = MediaFileUpload(file_path, resumable=True)

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id',
        supportsAllDrives=True
    ).execute()

    file_id = file.get('id')

    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"
    
def save_to_google(data):
    
    print("SAVE FUNCTION STARTED")

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    date_only = now.strftime("%Y-%m-%d")

    spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1ng2BZi-7_FeI7UUW55NcUP-oYZvrpAULB4FBp_baGFM/edit")

    manager = data["manager"]  
    
    try:
        sheet = spreadsheet.worksheet(manager)
    except:
        sheet = spreadsheet.add_worksheet(title=manager, rows="1000", cols="20")

        
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

            try:
               save_to_google(user_data[user_id])

               clear_user_state(user_id)
               user_state[user_id] = None
               user_data[user_id] = {}

               await message.answer(
                "Сохранено!",
                reply_markup=main_menu()
            )

            except Exception as e:
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