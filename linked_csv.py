import pandas as pd
import requests
import csv
from urllib.parse import urlencode


def get_resource_info(public_link):
    """
    Получение информации о ресурсах из API Яндекс.Диска.
    """
    base_url = 'https://cloud-api.yandex.net/v1/disk/public/resources?'
    final_url = base_url + urlencode(dict(public_key=public_link))
    response = requests.get(final_url)

    # Проверка успешности запроса
    if response.status_code != 200:
        raise ValueError(f"Ошибка получения данных: {response.status_code} - {response.text}")

    return response.json()


def extract_links_from_excel(input_excel, sheet_name):
    """
    Извлечение уникальных ссылок на Яндекс.Диск из Excel файла.
    """
    try:
        data = pd.read_excel(input_excel, sheet_name=sheet_name)
        # Извлечение столбца с ссылками и удаление дубликатов
        unique_links = data['Местоположение файлов'].drop_duplicates(keep='first').tolist()
        return unique_links
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл '{input_excel}' не найден.")
    except KeyError:
        raise KeyError(f"Столбец 'Местоположение файлов' отсутствует в листе '{sheet_name}'.")
    except Exception as e:
        raise Exception(f"Произошла ошибка: {e}")


def create_direct_links_csv(input_excel, sheet_name, output_csv):
    """
    Создание CSV файла с прямыми ссылками на файлы из Excel файла.

    :param input_excel: Путь к Excel файлу.
    :param sheet_name: Название листа в Excel файле.
    :param output_csv: Имя создаваемого файла CSV.
    """
    try:
        links = extract_links_from_excel(input_excel, sheet_name)
        print(f"Cоздание CSV файла '{output_csv}'...")

        with open(output_csv, 'w', encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=",")
            writer.writerow(["ID", "phase", "file_name", "link"]) # Добавляем строку с названиями колонок

            for href in links:
                try:
                    resource_info = get_resource_info(href)
                    if '_embedded' in resource_info:
                        items = resource_info['_embedded']['items']
                        for item in items:
                            if item['type'] == 'file':
                                folder = item['name'].split("_")[0][2:] if "_" in item['name'] else "Unknown"
                                # Разделяем строку на основе "_" и обрабатываем последний элемент до точки
                                if "_" in item['name']:
                                    parts = item['name'].split("_")
                                    if len(parts) > 1:
                                        phase = parts[1].split(".")[0]  # Извлекаем всё до точки
                                    else:
                                        phase = "Unknown"
                                else:
                                    phase = "Unknown"

                                filename = item['name'][:-4]
                                download_link = item['file'] if 'file' in item else None

                                if download_link:
                                    writer.writerow([folder, phase, filename, download_link])
                except Exception as e:
                    print(f"Ошибка обработки ссылки {href}: {e}")

        print(f"CSV файл '{output_csv}' успешно создан.")

    except Exception as e:
        print(f"Произошла ошибка: {e}")


if __name__ == "__main__":
    input_excel = 'data/База данных МСКТ надпочечников_MP4.xlsx'  # Укажите путь к вашему Excel файлу
    sheet_name = 'Лист1'  # Укажите имя листа в Excel
    output_csv = 'direct_links.csv'  # Имя выходного файла CSV

    create_direct_links_csv(input_excel, sheet_name, output_csv)

