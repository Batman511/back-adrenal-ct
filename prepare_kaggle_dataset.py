import os
import pandas as pd
import requests
import shutil
from tqdm import tqdm
import json
import cv2
import numpy as np
from linked_csv import *
from download_test import download_file_from_csv

def create_folder_structure():
    base_path = os.path.dirname(os.path.abspath(__file__))

    file_types = ["videos", "masks"]
    model_type = ["classification", "segmentation"]
    diagnosis = ['benign', 'malignant', 'indeterminate']

    # for exam in examination:
    for type in model_type:
        if type == 'classification':
            for diag in diagnosis:
                for filee in file_types:
                    folder_path = os.path.join(base_path, 'data', type, diag, filee)
                    os.makedirs(folder_path, exist_ok=True)
        else:
            for filee in file_types:
                folder_path = os.path.join(base_path, 'data', type, filee)
                os.makedirs(folder_path, exist_ok=True)

    print(f"Структура папок успешно создана в: {os.path.join(base_path, 'data')}")

format_base = {"id": [],
               "type": [],
               "video_path": [],
               "mask_path": [],
               "diagnosis": [],
               "localization": [],
               "phase": []}

format_classification = format_base
format_segmentation = format_base

def convert_video_to_npy(video_path, output_folder):
    """
    Конвертирует видео файл в .npy массив кадров в grayscale.

    :param video_path: Путь к видео файлу
    :param output_folder: Папка для сохранения .npy файла
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Ошибка: не удалось открыть видео файл {video_path}")
        return

    frames = []

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        # Конвертируем в grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray_frame)

    cap.release()

    if len(frames) == 0:
        print("Ошибка: не удалось прочитать ни одного кадра из видео")
        return

    frames_array = np.array(frames)

    # Создаем имя для .npy файла на основе имени видео
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    npy_filename = f"{base_name}.npy"
    npy_path = os.path.join(output_folder, npy_filename)

    # Сохраняем .npy файл
    np.save(npy_path, frames_array)
    # print(f"Видео успешно конвертировано в {npy_filename}")
    # print(f"Размер массива: {frames_array.shape} (кадры, высота, ширина)")

def download_and_convert_to_npy(file_name, download_link, download_folder):
    """
    Скачивает файл по указанной ссылке, конвертирует в .npy и удаляет оригинал.
    Защита от неверного имени файла (nan, float и т.п.) и от отсутствия ссылки.
    """
    # Защита от неверного имени файла
    if not isinstance(file_name, str) or not file_name or pd.isna(file_name):
        print(f"Пропускаю скачивание — неверное имя файла: {file_name}")
        return

    # Защита от отсутствующей/некорректной ссылки
    if not isinstance(download_link, str) or not download_link or pd.isna(download_link):
        print(f"Пропускаю скачивание {file_name} — отсутствует или неверная ссылка: {download_link}")
        return

    # Добавляем расширение .mp4 если отсутствует
    if not file_name.lower().endswith('.mp4'):
        file_name += '.mp4'

    if not os.path.exists(download_folder):
        print("Такой папки нет!")
        return

    # Скачиваем файл — с обработкой исключений сети
    file_path = os.path.join(download_folder, file_name)
    try:
        response = requests.get(download_link, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при подключении к {download_link} для файла {file_name}: {e}")
        return

    if response.status_code == 200:
        with open(file_path, 'wb') as output_file:
            output_file.write(response.content)
        # Конвертируем видео в .npy
        convert_video_to_npy(file_path, download_folder)

        # Удаляем оригинальный .mp4 файл
        try:
            os.remove(file_path)
        except OSError:
            pass
    else:
        print(f"Ошибка при скачивании файла {file_name}: {response.status_code} — пропускаю.")

def type_loader(type, row, base_path, format_file):
    if pd.notna(row['Ссылка на Файл c нативной фазой']) and pd.notna(row['Ссылка на Файл с разметкой нативной фазы']):
        videopath_cl_in_dataset = base_path + type + "/videos"
        download_and_convert_to_npy(
            file_name=row['Файл c нативной фазой'],
            download_link=row['Ссылка на Файл c нативной фазой'],
            download_folder=videopath_cl_in_dataset)

        maskpath_cl_in_dataset = base_path + type + "/masks"
        download_and_convert_to_npy(
            file_name=row['Файл с разметкой нативной фазы'],
            download_link=row['Ссылка на Файл с разметкой нативной фазы'],
            download_folder=maskpath_cl_in_dataset)

        format_file['id'].append(row['ID пациента'])
        format_file['type'].append(type)
        format_file['video_path'].append(videopath_cl_in_dataset)
        format_file['mask_path'].append(maskpath_cl_in_dataset)
        format_file['diagnosis'].append(row['Вероятный диагноз по КТ'])
        format_file['localization'].append(row['Локализация надпочечника (слева/справа)'])
        format_file['phase'].append("native")

    if pd.notna(row['Ссылка на Файл c артериальной фазой']) and pd.notna(row['Ссылка на Файл c разметкой артериальной фазы']):
        videopath_cl_in_dataset = base_path + type + "/videos"
        download_and_convert_to_npy(
            file_name=row['Файл c артериальной фазой'],
            download_link=row['Ссылка на Файл c артериальной фазой'],
            download_folder=videopath_cl_in_dataset)

        maskpath_cl_in_dataset = base_path + type + "/masks"
        download_and_convert_to_npy(
            file_name=row['Файл c разметкой артериальной фазы'],
            download_link=row['Ссылка на Файл c разметкой артериальной фазы'],
            download_folder=maskpath_cl_in_dataset)

        format_file['id'].append(row['ID пациента'])
        format_file['type'].append(type)
        format_file['video_path'].append(videopath_cl_in_dataset)
        format_file['mask_path'].append(maskpath_cl_in_dataset)
        format_file['diagnosis'].append(row['Вероятный диагноз по КТ'])
        format_file['localization'].append(row['Локализация надпочечника (слева/справа)'])
        format_file['phase'].append("arterial")

    if pd.notna(row['Ссылка на Файл c венозной фазой']) and pd.notna(row['Ссылка на Файл c разметкой венозной фазы']):
        videopath_cl_in_dataset = base_path + type + "/videos"
        download_and_convert_to_npy(
            file_name=row['Файл c венозной фазой'],
            download_link=row['Ссылка на Файл c венозной фазой'],
            download_folder=videopath_cl_in_dataset)

        maskpath_cl_in_dataset = base_path + type + "/masks"
        download_and_convert_to_npy(
            file_name=row['Файл c разметкой венозной фазы'],
            download_link=row['Ссылка на Файл c разметкой венозной фазы'],
            download_folder=maskpath_cl_in_dataset)

        format_file['id'].append(row['ID пациента'])
        format_file['type'].append(type)
        format_file['video_path'].append(videopath_cl_in_dataset)
        format_file['mask_path'].append(maskpath_cl_in_dataset)
        format_file['diagnosis'].append(row['Вероятный диагноз по КТ'])
        format_file['localization'].append(row['Локализация надпочечника (слева/справа)'])
        format_file['phase'].append("venous")

    if pd.notna(row['Ссылка на Файл c отсроченной фазой']) and pd.notna(row['Ссылка на Файл c разметкой отсроченной фазы']):
        videopath_cl_in_dataset = base_path + type + "/videos"
        download_and_convert_to_npy(
            file_name=row['Файл c отсроченной фазой'],
            download_link=row['Ссылка на Файл c отсроченной фазой'],
            download_folder=videopath_cl_in_dataset)

        maskpath_cl_in_dataset = base_path + type + "/masks"
        download_and_convert_to_npy(
            file_name=row['Файл c разметкой отсроченной фазы'],
            download_link=row['Ссылка на Файл c разметкой отсроченной фазы'],
            download_folder=maskpath_cl_in_dataset)

        format_file['id'].append(row['ID пациента'])
        format_file['type'].append(type)
        format_file['video_path'].append(videopath_cl_in_dataset)
        format_file['mask_path'].append(maskpath_cl_in_dataset)
        format_file['diagnosis'].append(row['Вероятный диагноз по КТ'])
        format_file['localization'].append(row['Локализация надпочечника (слева/справа)'])
        format_file['phase'].append("delay")

def excel_to_dataset(excel_file, links_csv_file):
    """
    Перенос данных из Excel-файла в коллекцию MongoDB с добавлением поля с локальным путем в файловой системе, а также ссылкой на скачивание.

    :param excel_file: Путь к Excel-файлу.
    :param links_csv_file: Путь к CSV файлу с прямыми ссылками.
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

    # print(df.columns)
    df.to_csv('dataframe.csv', index=False)

    base_path_classification = "data/classification"
    base_path_segmentation = "data/segmentation"

    for idx, row in tqdm(df.iterrows(), leave=True, total=len(df)):
        try:
            # Классификация
            if row['Доброкачественный КТ фенотип'] == 1:
                type = "/benign"
                type_loader(type, row, base_path_classification, format_classification)

            if row['Неопределенный КТ фенотип'] == 1:
                type = "/indeterminate"
                type_loader(type, row, base_path_classification, format_classification)


            if row['Злокачественный КТ фенотип'] == 1:
                type = "/malignant"
                type_loader(type, row, base_path_classification, format_classification)

            # # Сегментация
            type_loader('', row, base_path_segmentation, format_segmentation)

        except Exception as e:
            print(f"ID {idx} Не удалось скачать {row['ID пациента']}: {e}")


    with open('data/classification/format.json', 'w', encoding='utf-8') as f:
        json.dump(format_classification, f, ensure_ascii=False, indent=4)

    with open('data/segmentation/format.json', 'w', encoding='utf-8') as f:
        json.dump(format_segmentation, f, ensure_ascii=False, indent=4)

create_folder_structure()

excel_base_path = os.path.join(os.path.dirname(__file__), r'База данных МСКТ надпочечников_MP4.xlsx')

                # Создание CSV файла с прямыми ссылками на скачивание файлов из Excel файла. Время формирования = 3.8 записи/сек
                # create_direct_links_csv(excel_base_path, sheet_name='Лист1', output_csv='direct_links.csv')
links_csv_path = os.path.join(os.path.dirname(__file__), r'direct_links.csv')

excel_to_dataset(excel_file=excel_base_path, links_csv_file=links_csv_path)

shutil.make_archive('data', 'zip', 'data')

