import os, random, string, io, logging, hashlib, base64, glob
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort, url_for
from cryptography.fernet import Fernet
from logging.handlers import TimedRotatingFileHandler
from waitress import serve

app = Flask(__name__)

# Папка для хранения загруженных изображений
BASE_UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Установите максимальный размер файла в 5 МБ
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 МБ в байтах

# Настройка логирования
handler = TimedRotatingFileHandler('app.log', when='D', interval=1, backupCount=7) 
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Проверяем, существует ли базовая папка для загрузок, и создаем её, если нет
if not os.path.exists(BASE_UPLOAD_FOLDER):
    os.makedirs(BASE_UPLOAD_FOLDER)

# Функция для генерации случайного имени файла (8 символов)
def generate_link():
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

def decodelink(link: str):
    keyhash = hashlib.sha256(link.encode()).hexdigest()
    key = base64.urlsafe_b64encode(bytes.fromhex(keyhash))
    file = hashlib.sha256(keyhash.encode()).hexdigest()[:16]
    return file, key

def find_full_file_path(file_path_without_ext):
    # Получаем директорию файла
    directory = os.path.dirname(file_path_without_ext)
    # Получаем имя файла без расширения
    file_name = os.path.basename(file_path_without_ext)
    
    # Используем glob для поиска файлов с таким же именем, но любым расширением
    search_pattern = os.path.join(directory, file_name + '.*')
    found_files = glob.glob(search_pattern)
    
    if found_files:
        # Возвращаем первый найденный файл
        return found_files[0], os.path.basename(found_files[0])
    else:
        return None

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
    
    link = generate_link()

    filename_without_ext, key = decodelink(link)

    # Генерация случайного имени файла и создание папки на основе текущей даты
    filename =filename_without_ext + os.path.splitext(file.filename)[1]
    folder_path = create_date_folder()
    file_path = os.path.join(folder_path, filename)
    
    # Сохранение изображения
    file.save(file_path)
       
    # Шифрование файла
    encrypt_file(file_path, key)
    
    # Генерация ссылки с паролем
    image_url = url_for('view_link', year=datetime.now().year, month=datetime.now().month, day=datetime.now().day, link=link, _external=True)

    # Логирование события загрузки файла
    logging.info(f"POST {filename}, IP: {request.remote_addr}")
    
    return jsonify({'image_url': image_url})

@app.route('/<int:year>/<int:month>/<int:day>/<link>', methods=['GET'])
def view_link(year, month, day, link):
    
    filename_without_ext, key = decodelink(link)

    # Путь к зашифрованному файлу
    file_path, filename = find_full_file_path(os.path.join(app.config['UPLOAD_FOLDER'], str(year), str(month), str(day), filename_without_ext))
    
    if not os.path.exists(file_path):
        abort(404, description="Файл не найден.")
    
    try:
        # Попытка расшифровки файла
        decrypted_data = decrypt_file(file_path, key)
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

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'Размер файла превышает 5 МБ'}), 413

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=5000)
