import os
import pandas as pd
import requests
import shutil
import cv2
import numpy as np
from pymongo import MongoClient

def create_folder_structure(base_path:str) -> None:
    """
    Создает иерархию папок для хранения mp4-файлов

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


def check_images_in_excel(image_dir, excel_file, column_d='Файл c нативной фазой', column_t='Присутствует в папке "Все картинки"'):
    """
    Функция проверяет, присутствуют ли имена картинок из папки в Excel-файле и обновляет Excel:
    - Если имя картинки найдено в столбце D, ставит 1 в столбце T.
    - Картинки, не найденные в Excel, записывает в отдельный список.

    Возвращает:
        missing_images (list): Список картинок, которые не найдены в Excel-файле.
    """

    # Проверка существования пути к папке с изображениями
    if not os.path.isdir(image_dir):
        print(f"Ошибка: Путь к папке с изображениями '{image_dir}' не существует.")
        return []

    # Проверка существования Excel-файла
    if not os.path.isfile(excel_file):
        print(f"Ошибка: Excel-файл '{excel_file}' не найден.")
        return []

    # Попытка загрузить Excel-файл
    try:
        df = pd.read_excel(excel_file)
    except Exception as e:
        print(f"Ошибка при открытии Excel-файла: {e}")
        return []

    # Проверка наличия столбцов
    if column_d not in df.columns or column_t not in df.columns:
        print(f"Ошибка: В Excel-файле нет столбцов '{column_d}' или '{column_t}'.")
        return []

    # Преобразуем имена картинок из столбца D в список для удобства поиска
    excel_images = df[column_d].astype(str).tolist()

    # Список картинок, которые не найдены в Excel
    missing_images = []

    # Проходим по всем картинкам в папке
    for image_name in os.listdir(image_dir):
        # Убираем расширение файла (например, .jpg или .png) для сравнения
        image_base_name = os.path.splitext(image_name)[0]

        if image_base_name in excel_images:
            # Если имя картинки найдено, ставим 1 в столбец T
            df.loc[df[column_d] == image_base_name, column_t] = 1
        else:
            # Если не найдено, добавляем в список
            missing_images.append(image_name)

    # Попытка сохранить Excel-файл
    try:
        df.to_excel(excel_file, index=False)
    except Exception as e:
        print(f"Ошибка при сохранении Excel-файла: {e}")
        return []

    return missing_images

def delete_videos(video_dir, video_list):
    """
    Удаляет видеофайлы из указанной папки по названиям, которые переданы в списке.
    """
    for video_name in video_list:
        video_path = os.path.join(video_dir, video_name)
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
                print(f"Удалено: {video_path}")
            except OSError as e:
                print(f"Ошибка при удалении {video_path}: {e}")
        else:
            print(f"Файл не найден: {video_path}")


# С этим пока проблема. Не может загрузить файл по ссылке, с API Яндекс.Диска тоже не вышло.
def test_download_and_display_single_video(excel_file, column_names):
    """
    Функция для тестирования: загружает и отображает видеофайл с Яндекс.Диска по ссылке из excel-файла.
    """

    df = pd.read_excel(excel_file)
    row = df.iloc[1]
    base_link = row['Местоположение файлов']

    for col_name in column_names:
        file_name = f"{row[col_name]}.mp4"
        full_video_link = f"{base_link}/{file_name}"  # Полная ссылка
        print(f"Полная ссылка на видео: {full_video_link}")

        # Загрузка видео по прямой ссылки
        try:
            print(f"Загрузка файла: {file_name}")

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(full_video_link, headers=headers, stream=True)


            if response.status_code == 200:
                # Сохранение загруженного видео во временный файл
                temp_file = 'temp_video.mp4'
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                file_size = os.path.getsize(temp_file)
                print(f"Размер загруженного файла: {file_size} байт")

                if file_size == 0:
                    print(f"Ошибка: загруженный файл {file_name} пуст.")
                    continue

                # Открываем временный видеофайл и показываем первый кадр
                cap = cv2.VideoCapture(temp_file)
                if not cap.isOpened():
                    print(f"Не удалось открыть видеофайл: {temp_file}")
                    continue

                ret, frame = cap.read()
                if ret:
                    cv2.imshow(f'Первый кадр видео: {file_name}', frame)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()
                else:
                    print(f"Не удалось прочитать первый кадр из видео: {file_name}")

                # Освобождаем ресурсы
                cap.release()
            else:
                print(f"Ошибка при загрузке файла: {response.status_code}")
                continue
        except Exception as e:
            print(f"Ошибка загрузки файла: {e}")
            continue

def display_video(video_path, frame_skip=5, wait_key=200):
    """
    Функция для воспроизведения каждого {frame_skip} кадра видео с задержкой  {wait_key} мс.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Не удалось открыть видеофайл: {video_path}")
        return

    frame_count = 0  # Счётчик кадров
    window_name = 'Display_video'


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

# плохо работает
def display_video_with_max_contour(video_path, frame_skip=5, wait_key=400):
    """
    Функция находит максимальный контур на каждом {frame_skip} кадре,
    проводит вертикальную линию через центр контура и выводит кадры в одном окне, чтобы убедиться, что центр найден
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
def manual_directory_check(videos_dir):
    """
        Функция проверяет каждое видео из {videos_dir} с использованием display_video_with_center()
    """

    for file_name in os.listdir(videos_dir):
        video_path = os.path.join(videos_dir, file_name)

        if os.path.isfile(video_path) and file_name.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            display_video_with_center(video_path)

# заполняем папку data
def copy_videos_from_excel(excel_path, video_dir, data_dir):
    """
    Функция перемещает видео из папки video_dir в папку data, согласно Excel-файлу.

    Параметры:
        excel_path (str): Путь к Excel-файлу
        video_dir (str): Путь к директории, в которой хранятся исходные видео.
        data_dir (str): Путь к корневой папке, в которой будут создаваться директории для файлов.

    Возвращает:
        list: Список файлов, которые не были найдены в video_dir.
    """

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Ошибка при чтении файла Excel: {e}")
        return []

    not_found_files = []

    # Проходим по каждой строке таблицы
    for index, row in df.iterrows():
        file_name = row['Файл c нативной фазой'] + '.mp4'  # Имя видео
        target_subdir = row['Путь']


        source_path = os.path.join(video_dir, file_name)
        target_path = os.path.join(data_dir, target_subdir)


        if os.path.exists(source_path):

            # Полный путь к новому местоположению видео
            target_file_path = os.path.join(target_path, file_name)

            # Перемещаем файл, если его еще нет в целевой папке
            if not os.path.exists(target_file_path):
                try:
                    shutil.copy2(source_path, target_file_path)
                    print(f"Видео {file_name} успешно перемещено в {target_file_path}")
                except Exception as e:
                    print(f"Ошибка при перемещении {file_name}: {e}")
            else:
                print(f"Видео {file_name} уже находится в {target_file_path}")
        else:
            print(f"Видео {file_name} не найдено в {video_dir}")
            not_found_files.append(file_name)

    return not_found_files

# функция для загрузки и обработки видео с уменьшением количества и размера кадров.
def load_videos(data_dir, target_size=(240, 240), frame_skip=5, add_third_dimension=False):
    """
      Функция загружает видео из указанной директории, обрабатывает их (уменьшает количество кадров, уменьшает размер) и
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
        path = document["Путь"]  # Извлекаем локальный путь из документа -> заменить на ссылку в БД S3
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
    # create_folder_structure(r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture')
    test_download_and_display_single_video(r"C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\База данных МСКТ надпочечников_MP4.xlsx", column_names=['Файл c нативной фазой'])


    # video_path = r"C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\data\class02\ID5_NATIVE_SE1.mp4"
    # display_video(video_path,frame_skip=5, wait_key=200)
    # display_video_with_max_contour(video_path, frame_skip=5, wait_key=500) # не работает пока
    # display_video_with_center(video_path, frame_skip=5)

    data_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture\data'
    # videos, labels, label_names = load_videos(data_dir, target_size=(224, 224), frame_skip=5, add_third_dimension=True)
    # print(labels, label_names)




    # ----------------Проверяем все ли добавили при обновлении датасета (добавить в excel колонку "Присутствует в папке "Все картинки"")----------------#
    # image_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Все видео'  # Путь к папке с картинками
    # excel_file = r"C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\База данных МСКТ надпочечников_MP4 (1).xlsx"  # Путь к Excel-файлу
    #
    # missing_images = check_images_in_excel(image_dir, excel_file)
    # # Печать картинок, которых нет в Excel
    # print("Картинки, не найденные в Excel:", missing_images)





    # ----------------Проверял смещение----------------#
    # image_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Все картинки'
    # manual_directory_check(image_dir)


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





# ----------------Заполняем папку data при обновлении датасета (заполнить путь в excel)----------------#
#     = "data/" & ЕСЛИ(M2="слева"; "left_adrenal"; "right_adrenal") & "/class_" & N2 & "_" & O2 & "_" & P2
#     excel_path = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\База данных МСКТ надпочечников_MP4 (1).xlsx'
#     video_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Все видео'
#     data_dir = r'C:\Users\Антон\Documents\материалы ВИШ\Диплом КТ\Adrenal CT architecture'
#
#     # Вывод списка ненайденных файлов
#     not_found_files = copy_videos_from_excel(excel_path, video_dir, data_dir)
#     if not_found_files:
#         print("Видео, которые не были найдены:", not_found_files)
#     else:
#         print("Все видео найдены и скопированы.")




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