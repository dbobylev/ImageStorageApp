import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort, url_for
from cryptography.fernet import Fernet
import io
import logging

app = Flask(__name__)

# Папка для хранения загруженных изображений
BASE_UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Проверяем, существует ли базовая папка для загрузок, и создаем её, если нет
if not os.path.exists(BASE_UPLOAD_FOLDER):
    os.makedirs(BASE_UPLOAD_FOLDER)

# Функция для генерации случайного имени файла (8 символов)
def generate_filename():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

# Функция для генерации 8-символьного пароля
def generate_short_key():
    return Fernet.generate_key()

# Функция для создания папки на основе текущей даты
def create_date_folder():
    current_date = datetime.now()
    year_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_date.year))
    month_folder = os.path.join(year_folder, str(current_date.month))
    day_folder = os.path.join(month_folder, str(current_date.day))
    
    # Создаем папки, если они не существуют
    os.makedirs(day_folder, exist_ok=True)
    
    return day_folder

# Шифрование файла
def encrypt_file(file_path, key):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data)
    
    with open(file_path, 'wb') as f:
        f.write(encrypted_data)

# Расшифровка файла
def decrypt_file(file_path, key):
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<int:year>/<int:month>/<int:day>/<filename>', methods=['GET'])
def view_image(year, month, day, filename):
    password = request.args.get('p')
    
    if not password:
        abort(400, description="Не указан пароль для расшифровки.")
    
    # Путь к зашифрованному файлу, используя год, месяц и день из URL
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(year), str(month), str(day), filename)
    
    if not os.path.exists(file_path):
        abort(404, description="Файл не найден.")
    
    try:
        # Попытка расшифровки файла
        decrypted_data = decrypt_file(file_path, password.encode('utf-8'))
    except Exception as e:
        abort(400, description="Неверный пароль или ошибка расшифровки.")
    
    # Логирование события запроса файла
    logging.info(f"Запросили файл {filename}, IP: {request.remote_addr}, Время: {datetime.now()}")

    # Отправка изображения пользователю
    return send_file(
        io.BytesIO(decrypted_data), 
        mimetype='image/png' if filename.endswith('.png') else 'image/jpeg', 
        as_attachment=False,
        download_name=filename
    )


if __name__ == '__main__':
    app.run(debug=True)
