import sys
import io
# Настройка UTF-8 кодировки для вывода в консоль Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import csv
import json
import time

# --- НАСТРОЙКИ ---
# Вставьте сюда ваш API-ключ от Яндекс.Поиска по организациям
API_KEY = "097cf705-148d-4a8f-be8d-30bf39e0c341"

# Поисковый запрос (например: "автосервис Казань", "салон красоты Самара")
QUERY = "Ra nails Казань"

# Имя выходного CSV файла
OUTPUT_FILE = "yandex_organizations.csv"

# Сколько результатов нужно собрать (максимум за один запрос возвращается до 50)
LIMIT_RESULTS = 200 
# ------------------

def fetch_yandex_data(query, api_key, limit=100):
    url = "https://search-maps.yandex.ru/v1/"
    results = []
    skip = 0
    page_size = 50  # Максимальный лимит за 1 запрос у Яндекса

    print(f"Начинаю сбор данных по запросу: '{query}'...")

    while len(results) < limit:
        current_limit = min(page_size, limit - len(results))
        params = {
            "apikey": api_key,
            "text": query,
            "lang": "ru_RU",
            "type": "biz",
            "results": current_limit,
            "skip": skip
        }

        try:
            response = requests.get(url, params=params)
            if response.status_code == 403:
                print("Ошибка 403: Неверный API-ключ или превышен суточный лимит запросов.")
                break
            
            response.raise_for_status()
            data = response.json()
            
            features = data.get("features", [])
            if not features:
                print("Сбор завершен: больше нет результатов.")
                break

            for feature in features:
                properties = feature.get("properties", {})
                company_meta = properties.get("CompanyMetaData", {})
                
                # Извлекаем данные
                name = company_meta.get("name", "Не указано")
                address = company_meta.get("address", "Не указано")
                
                # Телефоны (может быть несколько)
                phones_list = company_meta.get("Phones", [])
                phones = "; ".join([p.get("formatted", "") for p in phones_list]) if phones_list else "Не указано"
                
                # Сайт
                url_site = company_meta.get("url", "Нет сайта")
                
                # Категории
                categories_list = company_meta.get("Categories", [])
                categories = ", ".join([c.get("name", "") for c in categories_list]) if categories_list else "Не указано"

                results.append({
                    "Название": name,
                    "Категория": categories,
                    "Сайт": url_site,
                    "Телефон": phones,
                    "Адрес": address
                })

            print(f"Собрано {len(results)} из {limit}...")
            
            # Сдвиг для следующей страницы
            skip += len(features)
            
            # Небольшая пауза между запросами
            time.sleep(0.5)

        except Exception as e:
            print(f"Произошла ошибка при запросе: {e}")
            break

    return results

def save_to_csv(data, filename):
    if not data:
        print("Нет данных для сохранения.")
        return

    keys = data[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    print(f"Данные успешно сохранены в файл: {filename}")

if __name__ == "__main__":
    if API_KEY == "ВАШ_API_КЛЮЧ_СЮДА":
        print("Внимание! Пожалуйста, замените 'ВАШ_API_КЛЮЧ_СЮДА' на реальный ключ API Яндекса.")
    else:
        results = fetch_yandex_data(QUERY, API_KEY, LIMIT_RESULTS)
        save_to_csv(results, OUTPUT_FILE)
