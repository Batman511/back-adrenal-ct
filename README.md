# back-adrenal-ct
backend-часть НИР "Диагностика заболеваний (образований) надпочечников с помощью ИИ", включающую в себя парсинг, обработку данных и работу с моделями

Ветка feature/preprocessing-raw-storage служит для скачивания видео-данных из сформированного врачами excel-файла, формирования БД MongoDB и преобразования данных в формат numpy-массивов для решения задачи классификации.

1. Надо работать с data_prepare.py, предварительно установив библиотеки из requirements.txt

     2.1. Прописать
     user_interface('create local structure')
     user_interface('create MongoDB database')
     user_interface('download files from DB to local PC')
     user_interface('data processing for classification and save')
   
     2.2. Прописать в user_interface интересующие команды

3. После получения трех файлов .npy необходимо загрузить их в датасет Kaggle и начать обучение моделей
