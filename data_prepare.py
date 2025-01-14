import os
import pandas as pd
import requests
import shutil
import cv2
import numpy as np
from pymongo import MongoClient
from linked_csv import *
from download_test import download_file_from_csv

def create_folder_structure():
    """
    Создает иерархию папок на локальной машине для хранения и дальнейших преобразований mp4-файлов

    Структура папок:
    base_path/
        └── data/
            ├── left_adrenal/
            │   ├── class_0_0_0/
            │   ├── class_0_0_1/
            │   ├── class_0_1_0/
                ...
            │   └── class_1_1_1/
            └── right_adrenal/
                ├── class_0_0_0/
                ├── class_0_0_1/
                ├── class_0_1_0/
                ...
                └── class_1_1_1/
    """
    base_path = os.path.dirname(os.path.abspath(__file__))

    class_combinations = [
        'class_0_0_0', 'class_0_0_1', 'class_0_1_0', 'class_0_1_1',
        'class_1_0_0', 'class_1_0_1', 'class_1_1_0', 'class_1_1_1'
    ]
    locations = ['left_adrenal', 'right_adrenal']

    for location in locations:
        for class_combination in class_combinations:
            folder_path = os.path.join(base_path, 'data', location, class_combination)
            os.makedirs(folder_path, exist_ok=True)

    print(f"Структура папок успешно создана в: {os.path.join(base_path, 'data')}")

def excel_to_mongodb_with_processing(excel_file, links_csv_file, database_name, collection_name, mongo_uri="mongodb://localhost:27017/"):
    """
    Перенос данных из Excel-файла в коллекцию MongoDB с добавлением поля с локальным путем в файловой системе, а также ссылкой на скачивание.

    :param excel_file: Путь к Excel-файлу.
    :param links_csv_file: Путь к CSV файлу с прямыми ссылками.
    :param database_name: Название базы данных MongoDB.
    :param collection_name: Название коллекции MongoDB.
    :param mongo_uri: URI для подключения к MongoDB (по умолчанию локальный сервер).
    """
    df = pd.read_excel(excel_file)
    direct_links_csv = pd.read_csv(links_csv_file)

    # Добавление колонки с адресом расположения в файловой системе локальной машины
    def generate_local_path(row):
        side = "left_adrenal" if row['Локализация надпочечника (слева/справа)'] == "слева" else "right_adrenal"
        return f"data/{side}/class_{row['Доброкачественный КТ фенотип']}_{row['Неопределенный КТ фенотип']}_{row['Злокачественный КТ фенотип']}"

    df['Локальный путь'] = df.apply(generate_local_path, axis=1)


    # Добавление ссылок из CSV файла в новые поля
    phase_columns = [
        "Файл c нативной фазой", "Файл с разметкой нативной фазы",
        "Файл c артериальной фазой", "Файл c разметкой артериальной фазы",
        "Файл c венозной фазой", "Файл c разметкой венозной фазы",
        "Файл c отсроченной фазой", "Файл c разметкой отсроченной фазы"
    ]
    for phase_column in phase_columns:
        link_column_name = f"Ссылка на {phase_column}"
        df[link_column_name] = pd.Series(dtype="object") #np.nan


    for idx, row in df.iterrows():
        patient_id = row["ID пациента"]

        for phase_column in phase_columns:
            if pd.notna(row[phase_column]):  # Проверка на непустое значение
                file_name = row[phase_column]

                match = direct_links_csv[    # Ищем совпадение в csv-файле
                    (direct_links_csv["ID"] == patient_id) &
                    (direct_links_csv["file_name"] == file_name)
                    ]
                if not match.empty:
                    link_column_name = f"Ссылка на {phase_column}"
                    df.at[idx, link_column_name] = match.iloc[0]["link"]



    # Подключение к MongoDB
    client = MongoClient(mongo_uri)
    db = client[database_name]
    collection = db[collection_name]

    # Преобразование данных DataFrame в список записей
    data = df.to_dict(orient='records')

    # Проверка наличия записей и добавление новых по полям "ID пациента" + "Локализация надпочечника (слева/справа)"
    new_records_count = 0   # Счётчик добавленных записей
    for record in data:
        query = {
            "ID пациента": record["ID пациента"],
            "Локализация надпочечника (слева/справа)": record["Локализация надпочечника (слева/справа)"]
        }
        if not collection.find_one(query):
            collection.insert_one(record)
            new_records_count += 1
        # else:
        #     collection.update_one(query, {"$set": record})  # Обновление существующих записей


    print(f"Данные успешно загружены в MongoDB.")
    print(f"Добавлено новых записей: {new_records_count}")
    print(f"Общее количество записей: {collection.count_documents({})}")

def display_video(video_path, file_name='', frame_skip=5, wait_key=200):
    """
    Воспроизведение каждого {frame_skip} кадра видео, находящегося по пути {video_path}, с задержкой {wait_key} мс между кадрами.

    :param video_path: Путь к видеофайлу.
    :param file_name: Имя файла (при необходимости).
    :param frame_skip: Количество кадров, которые будут пропускаться между отображаемыми (по умолчанию 5).
    :param wait_key: Время задержки в миллисекундах между отображением кадров (по умолчанию 200 мс).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Не удалось открыть видеофайл: {video_path}")
        return

    frame_count = 0  # Счётчик кадров
    window_name = f'Display_video {file_name}'


    while cap.isOpened():
        ret, frame = cap.read()

        if not ret:
            break  # Конец видео

        if frame_count % frame_skip == 0:
            cv2.imshow(window_name, frame) # Отображение кадра в одном и том же окне

            # Задержка между кадрами и Остановка при нажатии клавиши 'q'
            if cv2.waitKey(wait_key) & 0xFF == ord('q'):
                break

        frame_count += 1

    # Освобождение ресурсов
    cap.release()
    cv2.destroyAllWindows()

def download_file(file_name, download_link, download_folder):
    """
    Скачивает файл по указанной ссылке.

    :param file_name: Название файла для сохранения.
    :param download_link: Ссылка для скачивания файла.
    :param download_folder: Папка, в которую сохраняется файл.
    """
    if not file_name.endswith('.mp4'):
        file_name += '.mp4'

    if not os.path.exists(download_folder):
        # os.makedirs(download_folder)
        print("Такой папки нет!")
        return


    file_path = os.path.join(download_folder, file_name)
    response = requests.get(download_link)
    if response.status_code == 200:
        with open(file_path, 'wb') as output_file:
            output_file.write(response.content)
        # print(f"Файл {file_name} успешно скачан в папку {download_folder}.")
    else:
        print(f"Ошибка при скачивании файла {file_name}: {response.status_code} — {response.text}")

def download_files_from_mongo(db_name, collection_name, columns_to_download, mongo_uri="mongodb://localhost:27017/"):
    """
    Проверяет наличие файлов по локальному пути в MongoDB и скачивает отсутствующие.

    :param db_name: Имя базы данных MongoDB.
    :param collection_name: Имя коллекции MongoDB.
    :param columns_to_download: Список полей MongoDB, являющийся списком с фазами, которые нужно скачать.
    :param mongo_uri: URI для подключения к MongoDB.
    """
    print(f"Скачивание новых файлов начато...")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    base_path = os.path.dirname(__file__)
    downloaded_count = 0  # Счетчик скачанных файлов

    for record in collection.find():
        for column in columns_to_download:
            relative_local_path = record.get("Локальный путь", "")
            local_path = os.path.join(base_path, relative_local_path)

            file_name = record.get(column, "")
            if local_path and file_name:
                full_file_path = os.path.join(local_path, f"{file_name}.mp4")

                # Проверка наличия файла
                if not os.path.exists(full_file_path):
                    download_link = record.get(f"Ссылка на {column}", "")

                    if download_link:
                        # print(f"Скачиваем файл {file_name}")
                        download_file(file_name, download_link, local_path)
                        downloaded_count += 1
                    else:
                        print(f"Нет ссылки для скачивания файла {file_name}")

    print(f"Скачивание завершено. Всего скачано файлов: {downloaded_count}")


''' вряд ли понадобится, юзалось для проверки смещения'''
def display_video_with_max_contour(video_path, frame_skip=5, wait_key=400):
    """
    Функция находит максимальный контур на каждом {frame_skip} кадре,
    проводит вертикальную линию через центр контура и выводит кадры в одном окне, чтобы убедиться, что центр найден.
    РАБОТАЕТ ПЛОХО
    """

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Не удалось открыть видеофайл: {video_path}")
        return

    window_name = 'Display_video'
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Применяем размытие
            blurred = cv2.GaussianBlur(gray, (9, 9), 5)

            # Используем Canny для выделения границ
            edges = cv2.Canny(blurred, 50, 100)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                largest_contour = max(contours, key=cv2.contourArea)

                # Получаем момент для нахождения центра
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])

                    # Рисуем контур и линию на кадре
                    cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 2)
                    cv2.line(frame, (center_x, 0), (center_x, frame.shape[0]), (255, 0, 0), 2)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(wait_key) & 0xFF == ord('q'):  # 'q' для выхода
                break

        frame_count += 1

    cap.release()
    cv2.destroyAllWindows()
# проверяем что надпочечники на своих местах
def display_video_with_center(video_path, frame_skip=5, wait_key=200):
    """
    Функция проводит вертикальную линию через центр каждого {frame_skip} кадра для РУЧНОГО контроля того, что пациент не сместился. Выводит название файла.
    """

    file_name = os.path.splitext(os.path.basename(video_path))[0]


    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Не удалось открыть видеофайл: {video_path}")
        return

    window_name = 'Display_video'
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            height, width, _ = frame.shape

            center_x = width // 2
            cv2.line(frame, (center_x, 0), (center_x, height), (255, 0, 0), 2)

            # Выводим название файла на видео
            cv2.putText(frame, file_name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(wait_key) & 0xFF == ord('q'): # выход
                break

        frame_count += 1

    cap.release()
    cv2.destroyAllWindows()
def directory_check_with_center(videos_dir):
    """
        Функция проверяет каждое видео из {videos_dir} с использованием display_video_with_center()
    """

    for file_name in os.listdir(videos_dir):
        video_path = os.path.join(videos_dir, file_name)

        if os.path.isfile(video_path) and file_name.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            display_video_with_center(video_path)




# функция для загрузки и обработки видео с уменьшением количества и размера кадров. Вот тут можно экспериментировать!!
def load_videos(data_dir, target_size=(240, 240), frame_skip=5, add_third_dimension=False):
    """
      Функция загружает видео из директории {data_dir}, обрабатывает их (уменьшает количество кадров, уменьшает размер) и
      сохраняет в виде массивов.

      Возвращает:
          videos : Массив обработанных видео.
          labels : Массив меток классов. [0 0 1]
          label_names : Список имен меток. 'left_001'
      """

    """
    data_dir ='C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data'
    label_names =['left_adrenal', 'right_adrenal']
    class_names =['class_0_0_0', 'class_0_0_1', 'class_0_1_0', 'class_0_1_1', 'class_1_0_0', 'class_1_0_1', 'class_1_1_0', 'class_1_1_1']
    class_path ='C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data\\left_adrenal\\class_0_0_0'
    video_name ='ID100_NATIVE.mp4'
    video_path ='C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data\\left_adrenal\\class_0_0_0\\ID100_NATIVE.mp4'
    class_parts =['0', '0', '0']
    label =[np.uint8(0), np.uint8(0), np.uint8(0)]
    formatted_label_name ='left_000'
    video_name ='ID101_NATIVE.mp4'
    video_path ='C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data\\left_adrenal\\class_0_0_0\\ID101_NATIVE.mp4'
    class_parts =['0', '0', '0']
    """

    videos = []
    labels = []
    formatted_label_names = []
    label_names = os.listdir(data_dir) # ['left_adrenal', 'right_adrenal']

    for label_name in label_names:
        label_dir = os.path.join(data_dir, label_name)
        if 'left_adrenal' in label_name:
            prefix = 'left'
        elif 'right_adrenal' in label_name:
            prefix = 'right'
        else:
            continue


        class_names = os.listdir(label_dir) # ['class_0_0_0', 'class_0_0_1', 'class_0_1_0', 'class_0_1_1', 'class_1_0_0', 'class_1_0_1', 'class_1_1_0', 'class_1_1_1']
        for class_name in class_names:
            class_path = os.path.join(label_dir, class_name) # 'C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data\\left_adrenal\\class_0_0_0'
            for video_name in os.listdir(class_path): # for 'ID100_NATIVE.mp4'
                video_path = os.path.join(class_path, video_name) # 'C:\\Users\\Антон\\Documents\\материалы ВИШ\\Диплом КТ\\Adrenal CT architecture\\data\\left_adrenal\\class_0_0_0\\ID100_NATIVE.mp4'
                cap = cv2.VideoCapture(video_path)
                frames = []
                frame_count = 0
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_count % frame_skip == 0:
                        # Обрезаем изображение в зависимости от надпочечника
                        if prefix == 'left':
                            frame = frame[:, :frame.shape[1] // 2]
                        else:
                            frame = frame[:, frame.shape[1] // 2:]


                        frame = cv2.cvtColor(cv2.resize(frame, target_size), cv2.COLOR_BGR2GRAY)
                        if add_third_dimension:
                            frame = np.expand_dims(frame, axis=-1)  # Добавление канала для совместимости формы для некоторых моделей

                        frames.append(frame)
                    frame_count += 1
                cap.release()

                # Генерируем метку в виде массива из трех чисел
                class_parts = class_name.split('_')[1:] # ['0', '0', '0']
                label = [np.uint8(int(class_parts[i])) for i in range(3)] # [np.uint8(0), np.uint8(0), np.uint8(0)]

                # Генерируем имя метки в виде left_001 или right_001
                formatted_label_name = f"{prefix}_{''.join(class_parts)}" # 'left_000'

                videos.append(np.array(frames, dtype=np.uint8))
                labels.append(label)
                formatted_label_names.append(formatted_label_name)

    return np.array(videos, dtype=np.uint8), np.array(labels, dtype=np.int64), formatted_label_names


def load_videos_from_mongo(db_name, collection_name, data_dir, target_size=(240, 240), frame_skip=5, add_third_dimension=False):
    """
    Загружает видео из путей, указанных в MongoDB, обрабатывает их и возвращает массивы видео, меток и имен меток.

    Аргументы:
        db_name (str): Имя базы данных MongoDB.
        collection_name (str): Имя коллекции MongoDB.
        data_dir (str): Корневая директория для хранения данных.
        target_size (tuple): Размер, к которому нужно привести кадры видео.
        frame_skip (int): Количество кадров, которые нужно пропустить.
        add_third_dimension (bool): Флаг для добавления третьего измерения к кадрам.

    Возвращает:
        videos (np.array): Массив обработанных видео.
        labels (np.array): Массив меток.
        formatted_label_names (list): Список имен меток.
    """
    # Подключение к MongoDB локально или через песочницу
    client = MongoClient('mongodb://localhost:27017/')
    db = client[db_name]
    collection = db[collection_name]

    videos = []
    labels = []
    formatted_label_names = []

    # Получаем все документы из коллекции
    for document in collection.find():
        path = document["Локальный путь"]  # Извлекаем локальный путь из документа -> заменить на ссылку в БД S3
        full_path = data_dir + path

        if 'left_adrenal' in path:
            prefix = 'left'
        elif 'right_adrenal' in path:
            prefix = 'right'
        else:
            continue

        # только для локалки
        last_backslash_index = full_path.rfind('\\')
        class_name = full_path[last_backslash_index + 1:] # ['class_0_0_0']
        video_path = full_path + "\\" + document["Файл c нативной фазой"] + ".mp4"


        cap = cv2.VideoCapture(video_path)
        frames = []
        frame_count = 0 # для пропуска кадров
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_skip == 0:
                # Обрезаем изображение в зависимости от надпочечника
                if prefix == 'left':
                    frame = frame[:, :frame.shape[1] // 2]
                else:
                    frame = frame[:, frame.shape[1] // 2:]

                frame = cv2.cvtColor(cv2.resize(frame, target_size), cv2.COLOR_BGR2GRAY)
                # МОЖНО ДОБАВИТЬ ЕЩЕ ОБРАБОТКУ

                if add_third_dimension:
                    frame = np.expand_dims(frame, axis=-1) # Добавление канала для совместимости формы для некоторых моделей

                frames.append(frame)
            frame_count += 1
        cap.release()

        # Генерируем метку в виде массива из трех чисел
        class_parts = class_name.split('_')[1:] # ['0', '0', '0']
        label = [np.uint8(int(class_parts[i])) for i in range(3)] # [np.uint8(0), np.uint8(0), np.uint8(0)]

        # Генерируем имя метки в виде left_001 или right_001
        formatted_label_name = f"{prefix}_{''.join(class_parts)}"

        videos.append(np.array(frames, dtype=np.uint8))
        labels.append(label)
        formatted_label_names.append(formatted_label_name)

    return np.array(videos, dtype=np.uint8), np.array(labels, dtype=np.int64), np.array(formatted_label_names)



if __name__ == "__main__":
    ''' 0. Надо прописывать команды поочередно '''

    choice = 'download files from DB to local PC'
    match choice:
        case 'create local structure':
            # Создаем иерархию папок на локальной машине для хранения и дальнейших преобразований mp4-файлов
            create_folder_structure()

        case 'create MongoDB database':
            ''' 1. Предварительно установите MongoDBCompass, создайте БД и коллекцию'''

            excel_base_path = os.path.join(os.path.dirname(__file__), r'База данных МСКТ надпочечников_MP4.xlsx')

            # Создание CSV файла с прямыми ссылками на скачивание файлов из Excel файла. Время формирования = 3.8 записи/сек
            # create_direct_links_csv(excel_base_path, sheet_name='Лист1', output_csv='direct_links.csv')
            links_csv_path = os.path.join(os.path.dirname(__file__), r'direct_links.csv')

            # Преобразовываем данные из сырого ХД (excel-файл) в MongoDB, добавляя поле с путем до файла на локальной машине, а также поле с ссылкой на скачивание каждого файла
            excel_to_mongodb_with_processing(
                excel_file=excel_base_path,
                links_csv_file=links_csv_path,
                database_name="Adrenal_CT",
                collection_name="Data")

        case 'test download file by name':
            file_name = "ID53_ARTERIAL" # название файла для скачивания без типа

            # Проверка того, что прямые ссылки из csv-файла рабочие, а файлы скачиваются корректно
            download_file_from_csv(file_name, download_folder='ct_download')
            links_test_download_file = os.path.join(os.path.dirname(__file__), 'ct_download', f'{file_name}.mp4')
            display_video(links_test_download_file, file_name=file_name) # для закрытия нажимать 'q'

        case 'download files from DB to local PC':
            # Скачиваем недостающие файлы в локальную систему
            download_files_from_mongo(
                db_name="Adrenal_CT",
                collection_name="Data",
                columns_to_download=["Файл c нативной фазой"],
                mongo_uri="mongodb://localhost:27017/"
                )

        case _:
            print("Неизвестный выбор.")



    #     data_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\data'
    #     videos, labels, labels_names = load_videos(data_dir)
    #
    #     # Проверка результата
#     print(f"Форма массива видео: {videos.shape}")
#     print(f"Метки: {labels}")
#     print(f"Имена меток: {labels_names}")
#
#
#     first_video = videos[1]
#     window_name = 'Video Display'
#     cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
#
#     for i, frame in enumerate(first_video):
#         cv2.imshow(window_name, frame)
#
#         if cv2.waitKey(200) & 0xFF == ord('q'):
#             break
#
#     cv2.destroyAllWindows()






#----------------Преобразование данных----------------#
    # data_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\data'
    #
    #
    # videos, labels, labels_names = load_videos_from_mongo(
    #     db_name="Adrenal_CT",
    #     collection_name="Data",
    #     data_dir=data_dir,
    #     target_size=(224, 224),
    #     frame_skip=3,
    #     add_third_dimension=True
    # )
    # print(f"Форма массива видео: {videos.shape}")
    # assert videos.shape[0] == len(labels) == len(labels_names), "Все массивы должны иметь одинаковое количество элементов по первой оси!"
    #
    #
    # # Генерация случайного порядка индексов и перемешивание
    # shuffle_indices = np.random.permutation(videos.shape[0])
    # videos = videos[shuffle_indices]
    # labels = labels[shuffle_indices]
    # labels_names = labels_names[shuffle_indices]
    #
    #
    # # print(f"Метки: {labels}")
    # # print(f"Имена меток: {labels_names}")
    #
    #
    #
    # # Пути для сохранения файлов
    # videos_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\videos.npy'
    # labels_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\labels.npy'
    # labels_names_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\labels_names.npy'
    #
    # np.save(videos_file, videos)
    # np.save(labels_file, labels)
    # np.save(labels_names_file, labels_names)
    #
    # print("Массивы успешно сохранены.")


#----------------Загрузка массивов данных----------------#

    # videos_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\videos.npy'
    # labels_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\labels.npy'
    # labels_names_file = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\labels_names.npy'
    #
    # videos = np.load(videos_file)
    # labels = np.load(labels_file)
    # labels_names = np.load(labels_names_file)
    #
    # print(f"Форма массива видео: {videos.shape}")
    #
    # first_video = videos[0]
    # window_name = 'Video Display'
    # cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    #
    # for i, frame in enumerate(first_video):
    #     cv2.imshow(window_name, frame)
    #
    #     if cv2.waitKey(200) & 0xFF == ord('q'):
    #         break
    #
    # cv2.destroyAllWindows()