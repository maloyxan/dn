# Используем официальный образ Python 3.10 (он легкий и подходит для Aiogram 3)
FROM python:3.10-slim

# Устанавливаем рабочую папку внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы бота (main.py, картинку и т.д.)
COPY . .

# Команда для запуска бота
CMD ["python", "main.py"]
