import os
import uuid
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort, url_for
from cryptography.fernet import Fernet
import io
import logging
from waitress import serve

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

# Функция для создания папки на основе текущей даты
def create_date_folder():
    current_date = datetime.now()
    year_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_date.year))
    month_folder = os.path.join(year_folder, str(current_date.month))
    day_folder = os.path.join(month_folder, str(current_date.day))
    
    # Создаем папки, если они не существуют
    os.makedirs(day_folder, exist_ok=True)
    
    return day_folder

# Генерация ключа шифрования (ключ может быть различным для каждого файла)
def generate_key():
    return Fernet.generate_key()

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

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'Нет изображения в запросе'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Генерация случайного имени файла и создание папки на основе текущей даты
    filename = generate_filename() + os.path.splitext(file.filename)[1]
    folder_path = create_date_folder()
    file_path = os.path.join(folder_path, filename)
    
    # Сохранение изображения
    file.save(file_path)
    
    # Генерация ключа шифрования
    key = generate_key()
    
    # Шифрование файла
    encrypt_file(file_path, key)
    
    # Генерация ссылки с паролем
    image_url = url_for('view_image', year=datetime.now().year, month=datetime.now().month, day=datetime.now().day, filename=filename, _external=True)
    password = key.decode('utf-8')
    image_url_with_password = f"{image_url}?p={password}"

    # Логирование события загрузки файла
    logging.info(f"POST {filename}, IP: {request.remote_addr}")
    
    return jsonify({'image_url': image_url_with_password})

@app.route('/view/<int:year>/<int:month>/<int:day>/<filename>', methods=['GET'])
def view_image(year, month, day, filename):
    password = request.args.get('p')
    
    if not password:
        abort(400, description="Не указан пароль для расшифровки.")
    
    # Путь к зашифрованному файлу
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(year), str(month), str(day), filename)
    
    if not os.path.exists(file_path):
        abort(404, description="Файл не найден.")
    
    try:
        # Попытка расшифровки файла
        decrypted_data = decrypt_file(file_path, password.encode('utf-8'))
    except Exception as e:
        abort(400, description="Неверный пароль или ошибка расшифровки.")

    # Логирование события запроса файла
    logging.info(f"GET {filename}, IP: {request.remote_addr}")
    
    # Отправка изображения пользователю
    return send_file(
        io.BytesIO(decrypted_data), 
        mimetype='image/png' if filename.endswith('.png') else 'image/jpeg', 
        as_attachment=False,
        download_name=filename
    )

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=5000)
