import sys
import io
import csv
import time
from playwright.sync_api import sync_playwright

# Настройка UTF-8 для вывода в консоль
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- НАСТРОЙКИ ---
QUERY = "Ra nails Казань"
OUTPUT_FILE = "leads_to_contact.csv"
MAX_SCROLLS = 15  # Сколько раз прокрутить список вниз для загрузки новых компаний
LIMIT_ORGS = 15   # Сколько организаций детально спарсить (можно увеличить)
# ------------------

def analyze_website(site):
    if not site or site == "Нет сайта":
        return "Без сайта", "Высокий (Нет сайта)"
    
    site_lower = site.lower()
    
    # Проверка на социальные сети
    social_domains = ["vk.com", "vk.ru", "instagram.com", "t.me", "telegram", "facebook.com", "ok.ru", "gogol.ru"]
    if any(domain in site_lower for domain in social_domains):
        return "Соцсеть", "Высокий (Только соцсети)"
        
    # Проверка на бесплатные конструкторы / платформы визиток
    constructor_domains = ["clients.site", "tilda.ws", "taplink.cc", "wixsite.com", "setup.ru", "ucoz", "blogspot", "nethouse"]
    if any(domain in site_lower for domain in constructor_domains):
        return "Конструктор / Taplink", "Средний (Простой шаблон)"
        
    return "Собственный сайт", "Низкий (Есть сайт)"

def scrape_yandex_maps(query, max_scrolls, limit_orgs):
    print(f"Запуск браузера для поиска лидов по запросу: '{query}'...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Открываем Яндекс Карты с поисковым запросом
        url = f"https://yandex.ru/maps/?text={query}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        print("Ожидание загрузки результатов...")
        page.wait_for_timeout(5000)

        # Селектор панели с результатами поиска
        sidebar_selector = ".search-list-view__list"
        
        if not page.locator(sidebar_selector).is_visible():
            print("Внимание! Если на экране появилась капча Яндекса, пожалуйста, решите её в открывшемся окне браузера.")
            page.wait_for_selector(sidebar_selector, timeout=60000) # Ждем до 1 минуты решения капчи

        print("Начинаю прокрутку списка и динамический сбор ссылок...")
        org_urls = []
        
        # Скроллим боковую панель вниз и собираем ссылки на лету
        for i in range(max_scrolls):
            # Находим карточки на текущем экране
            cards = page.locator(".search-snippet-view").all()
            for card in cards:
                try:
                    link_overlay = card.locator(".link-overlay")
                    if link_overlay.count() > 0:
                        href = link_overlay.first.get_attribute("href")
                        if href and "/org/" in href:
                            full_url = f"https://yandex.ru{href.split('?')[0]}"
                            if full_url not in org_urls:
                                org_urls.append(full_url)
                except:
                    pass

            # Прокручиваем вниз
            scroll_js = """
            (() => {
                let el = document.querySelector('.search-list-view__list') || 
                         document.querySelector('.scroll__container') || 
                         document.querySelector('[class*="search-list-view"]');
                if (el) {
                    el.scrollTop = el.scrollTop + 1500;
                    return true;
                }
                return false;
            })()
            """
            page.evaluate(scroll_js)
            page.wait_for_timeout(1000)  # Ждем подгрузки новых компаний
            if (i + 1) % 3 == 0 or i == max_scrolls - 1:
                print(f"Шаг скроллинга {i+1}/{max_scrolls}... Собрано уникальных ссылок: {len(org_urls)}")

        print(f"Итого собрано уникальных ссылок на организации: {len(org_urls)}")
        
        results = []
        target_urls = org_urls[:limit_orgs]
        print(f"Начинаю прямой обход ссылок для {len(target_urls)} компаний...")
        
        for idx, org_url in enumerate(target_urls):
            try:
                print(f"[{idx+1}/{len(target_urls)}] Переход по адресу: {org_url}")
                page.goto(org_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
                # 1. Извлекаем название
                name = "Не указано"
                name_selectors = [
                    "h1.orgpage-header-view__header",
                    "h1.business-header-view__title",
                    ".orgpage-header-view__header-title",
                    "h1"
                ]
                for sel in name_selectors:
                    el = page.locator(sel)
                    if el.count() > 0:
                        name = el.first.text_content().strip()
                        break

                # 2. Извлекаем адрес
                address = "Не указано"
                address_selectors = [
                    ".business-contacts-view__address",
                    ".orgpage-header-view__address",
                    ".orgpage-contacts-view__address",
                    ".business-contacts-view__address-link",
                    "a[href*='address']"
                ]
                for sel in address_selectors:
                    el = page.locator(sel)
                    if el.count() > 0:
                        address = el.first.text_content().strip()
                        break

                # 3. Извлекаем сайт
                site = "Нет сайта"
                site_selectors = [
                    "a.business-urls-view__link",
                    "a.orgpage-contacts-view__website",
                    "a.orgpage-contacts-view__site",
                    ".orgpage-contacts-view__item_type_website a",
                    "a[href*='clck.yandex.ru']"
                ]
                for sel in site_selectors:
                    el = page.locator(sel)
                    if el.count() > 0:
                        href = el.first.get_attribute("href")
                        if href:
                            site = href
                            break
                            
                if site == "Нет сайта":
                    contacts_panel = page.locator(".orgpage-contacts-view, .business-contacts-view")
                    if contacts_panel.count() > 0:
                        links = contacts_panel.first.locator("a").all()
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "yandex" not in href and href.startswith("http"):
                                site = href
                                break

                # Анализируем сайт
                site_type, priority = analyze_website(site)

                if name != "Не указано":
                    name = " ".join(name.split())

                print(f" Успешно собрано: {name} | Сайт: {site} | Приоритет лида: {priority}")

                results.append({
                    "Название": name,
                    "Адрес": address,
                    "Ссылка в Картах": org_url,
                    "Сайт": site,
                    "Тип сайта": site_type,
                    "Приоритет лида": priority
                })

            except Exception as e:
                print(f" Ошибка при переходе/разборе {org_url}: {e}")
                continue

        browser.close()
        return results

def save_results(data, filename):
    if not data:
        print("Данные не собраны.")
        return
    
    # Фильтруем данные, оставляя только заведения БЕЗ сайта, с соцсетями или конструкторами
    leads = [row for row in data if row["Приоритет лида"] != "Низкий (Есть сайт)"]
    
    if not leads:
        print("Не найдено подходящих лидов без сайта или с простым сайтом.")
        leads = data

    keys = leads[0].keys()
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(leads)
    
    print(f"Сбор завершен! Всего проанализировано: {len(data)}")
    print(f"Найдено перспективных лидов (высокий/средний приоритет): {len(leads)}")
    print(f"Данные сохранены в файл: {filename}")

if __name__ == "__main__":
    try:
        data = scrape_yandex_maps(QUERY, MAX_SCROLLS, LIMIT_ORGS)
        save_results(data, OUTPUT_FILE)
    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")
