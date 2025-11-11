from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

def find_openbmc_web_interface():
    test_urls = ["https://localhost:2443"]

    options = Options()
    options.binary_location = '/usr/bin/chromium-browser'
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--disable-web-security')

    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)

    for url in test_urls:
        try:
            driver.get(url)
            time.sleep(3)

            page_title = driver.title.lower()
            page_source = driver.page_source.lower()

            openbmc_indicators = [
                'openbmc', 'bmc', 'login', 'authorization',
                'username', 'password', 'phosphor', 'redfish'
            ]

            found_indicators = [indicator for indicator in openbmc_indicators
                                if indicator in page_source or indicator in page_title]

            if found_indicators:
                return url, driver

        except Exception as e:
            print(f"Ошибка: {str(e)[:100]}")

    driver.quit()
    return None, None

def find_login_button(driver):
    login_selectors = [
        "button[type='submit']",
        "button.btn-login",
        "input[type='submit']",
        ".login-button"
    ]

    for selector in login_selectors:
        try:
            return driver.find_element(By.CSS_SELECTOR, selector)
        except NoSuchElementException:
            continue

    buttons = driver.find_elements(By.TAG_NAME, "button")
    if buttons:
        return buttons[0]

    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        if inp.get_attribute('type') == 'submit':
            return inp

    raise NoSuchElementException("Не найдена кнопка логина")

def test_correct_login():
    print("Тест успешной авторизации")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()

        time.sleep(5)

        current_url = driver.current_url.lower()
        page_title = driver.title.lower()

        assert "login" not in current_url, f"Остались на странице логина: {current_url}"
        assert "login" not in page_title, f"Заголовок содержит login: {page_title}"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_wrong_username():
    print("Тест авторизации с неверным именем пользователя")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("invalid_user")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()

        time.sleep(3)

        current_url = driver.current_url.lower()
        

        assert "login" in current_url, f"Не сработала валидация неверного имени пользователя: {current_url}"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_wrong_password():
    print("Тест авторизации с неверным паролем")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("wrong_password")
        login_button.click()

        time.sleep(3)

        current_url = driver.current_url.lower()

        assert "login" in current_url, f"Не сработала валидация неверного пароля: {current_url}"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_account_lockout():
    print("Тест проверки поведения при множественных неудачных попытках")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:

        for attempt in range(3):
            try:
                driver.refresh()
                time.sleep(1)
                username_field = driver.find_element(By.CSS_SELECTOR, "#username")
                password_field = driver.find_element(By.CSS_SELECTOR, "#password")
                login_button = find_login_button(driver)

                username_field.clear()
                username_field.send_keys("root")
                password_field.clear()
                password_field.send_keys(f"vou_{attempt}")
                login_button.click()
                time.sleep(2)
            except:
                continue

        driver.refresh()
        time.sleep(2)
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()
        time.sleep(5)
    except Exception as e:
        print(f"exception {e}")
    finally:
        driver.quit()

def test_power_management():
    print("Тест управления питанием сервера через WebUI")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()
        time.sleep(5)

        current_url = driver.current_url.lower()
        assert "login" not in current_url, "Не удалось войти в систему"

        power_management_found = False
        power_urls = [
            "/redfish/v1/Systems/system",
            "/ui/#/system",
            "/ui/system"
        ]

        for power_url in power_urls:
            try:
                full_url = url + power_url
                driver.get(full_url)
                time.sleep(3)

                page_source = driver.page_source.lower()

                if any(indicator in page_source for indicator in ["power", "reset", "shutdown", "reboot"]):
                    power_management_found = True
                    break

            except Exception:
                continue

        assert power_management_found, "Управление питанием не найдено в WebUI"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_redfish_api_access():
    print("Тест доступа к Redfish API через WebUI")
    

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()
        time.sleep(5)

        current_url = driver.current_url.lower()
        assert "login" not in current_url, "Не удалось войти в систему"

        redfish_found = False
        redfish_urls = [
            "/redfish/v1/",
            "/redfish",
            "/ui/#/redfish"
        ]

        for redfish_url in redfish_urls:
            try:
                full_url = url + redfish_url
                driver.get(full_url)
                time.sleep(3)

                page_source = driver.page_source.lower()

                if any(indicator in page_source for indicator in ["redfish", "odata", "json", "api"]):
                    redfish_found = True
                    break

            except Exception:
                continue

        assert redfish_found, "Redfish API не доступен через WebUI"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_temperature_monitoring():
    print("Тест мониторинга температуры")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()
        time.sleep(5)

        current_url = driver.current_url.lower()
        assert "login" not in current_url, "Не удалось войти в систему"

        temperature_found = False
        temperature_urls = [
            "/redfish/v1/Chassis/chassis/Thermal",
            "/ui/#/thermal",
            "/ui/thermal"
        ]

        for temp_url in temperature_urls:
            try:
                full_url = url + temp_url
                driver.get(full_url)
                time.sleep(3)

                page_source = driver.page_source.lower()

                if any(indicator in page_source for indicator in ["temperature", "thermal", "sensor"]):
                    temperature_found = True
                    break

            except Exception:
                continue

        assert temperature_found, "Мониторинг температуры не найден в WebUI"

    except Exception as e:
        raise e
    finally:
        driver.quit()

def test_inventory_display():
    print("Тест отображения инвенторика в Web UI")

    url, driver = find_openbmc_web_interface()
    assert url is not None, "Веб-интерфейс OpenBMC не найден"

    try:
        username_field = driver.find_element(By.CSS_SELECTOR, "#username")
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = find_login_button(driver)

        username_field.clear()
        username_field.send_keys("root")
        password_field.clear()
        password_field.send_keys("0penBmc")
        login_button.click()
        time.sleep(5)

        current_url = driver.current_url.lower()
        assert "login" not in current_url, "Не удалось войти в систему"

        inventory_indicators = [
            "//*[contains(text(), 'Inventory')]",
            "//*[contains(text(), 'Hardware')]",
            "//*[contains(text(), 'System')]",
            "//*[contains(text(), 'Configuration')]",
            "//*[contains(text(), 'CPU')]",
            "//*[contains(text(), 'Memory')]",
            "//*[contains(text(), 'Storage')]"
        ]
        

        inventory_found = False
        for indicator in inventory_indicators:
            try:
                inventory_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, indicator)))
                print(f"Найден элемент инвентори: {inventory_element.text}")
                inventory_found = True

                try:
                    inventory_element.click()
                    time.sleep(2)
                    print("Успешный переход к инвентори")
                    break
                except:
                    continue

            except TimeoutException:
                continue

        if not inventory_found:
            print("Элементы инвентори не найдены через XPath, пробуем через URL...")
            inventory_urls = [
                "/redfish/v1/Systems/system",
                "/ui/#/inventory",
                "/ui/inventory"
            ]

            for inventory_url in inventory_urls:
                try:
                    full_url = url + inventory_url
                    driver.get(full_url)
                    time.sleep(3)

                    page_source = driver.page_source.lower()

                    if any(indicator in page_source for indicator in ["cpu", "processor", "memory", "ram"]):
                        inventory_found = True
                        break

                except Exception as e:
                    continue

        assert inventory_found, "Инвентаризация не найдена в WebUI"

    except Exception as e:
        print(f" Отображение инвентори: ОШИБКА - {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    test_functions = [
        test_correct_login,
        test_wrong_username,
        test_wrong_password,
        test_account_lockout,
        test_power_management,
        test_redfish_api_access,
        test_temperature_monitoring,
        test_inventory_display
    ]

    passed_count = 0
    total_count = len(test_functions)

    for test_func in test_functions:
        try:
            test_func()
            print(f" {test_func.__name__} - PASSED")
            passed_count += 1
        except Exception as e:
            print(f" {test_func.__name__} - FAILED: {e}")

    print(f"Результат: {passed_count}/{total_count} тестов пройдено")