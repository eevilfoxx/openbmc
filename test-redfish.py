import pytest
import requests
import os
import time
import subprocess
import re
import json

# Базовые фикстуры
@pytest.fixture(scope="session")
def base_url():
    return os.getenv('OPENBMC_URL', 'https://localhost:2443')

@pytest.fixture(scope="session")
def credentials():
    return {
        'username': os.getenv('OPENBMC_USERNAME', 'root'),
        'password': os.getenv('OPENBMC_PASSWORD', '0penBmc')
    }

@pytest.fixture(scope="session")
def session(base_url, credentials):
    """Создает аутентифицированную сессию для всех тестов"""
    s = requests.Session()
    s.verify = False  # Отключаем проверку SSL для самоподписанных сертификатов
    s.auth = (credentials['username'], credentials['password'])
    return s

@pytest.fixture(scope="function")
def auth_session(base_url, credentials):
    """Создает новую аутентифицированную сессию через Redfish Session Service"""
    s = requests.Session()
    s.verify = False
    
    # Создаем сессию через Redfish Session Service
    auth_url = f"{base_url}/redfish/v1/SessionService/Sessions"
    auth_data = {
        "UserName": credentials['username'],
        "Password": credentials['password']
    }
    
    response = s.post(auth_url, json=auth_data)
    if response.status_code == 200:
        # Устанавливаем токен аутентификации для последующих запросов
        auth_token = response.headers.get('X-Auth-Token')
        if auth_token:
            s.headers.update({'X-Auth-Token': auth_token})
    else:
        pytest.fail(f"Не удалось создать сессию: {response.status_code}")
    
    return s

class TestOpenBMCComplete:
    """Полный набор тестов для OpenBMC Redfish API"""
    
    def test_01_redfish_authentication(self, base_url, credentials):
        """
        Тест аутентификации в OpenBMC через Redfish API
        ○ Отправить POST-запрос для создания сессии.
        ○ Проверить код ответа (200 при успешной аутентификации).
        ○ Убедиться, что токен сессии присутствует в ответе.
        """
        print("\n=== Тест аутентификации ===")
        
        # Создаем временную сессию без аутентификации для этого теста
        session = requests.Session()
        session.verify = False
        
        # Отправляем POST-запрос для создания сессии
        auth_url = f"{base_url}/redfish/v1/SessionService/Sessions"
        auth_data = {
            "UserName": credentials['username'],
            "Password": credentials['password']
        }
        
        response = session.post(auth_url, json=auth_data)
        
        # Проверяем код ответа (201 при успешной аутентификации)
        assert response.status_code == 201, f"Ожидался статус 201, получен {response.status_code}. Ответ: {response.text}"
        
        # Проверяем, что токен сессии присутствует в ответе
        response_data = response.json()
        assert 'Id' in response_data, "Токен сессии (Id) отсутствует в ответе"
        assert 'AuthToken' in response.headers or 'X-Auth-Token' in response.headers, "Токен аутентификации отсутствует в заголовках"
        
        session_id = response_data['Id']
        auth_token = response.headers.get('X-Auth-Token', response.headers.get('AuthToken'))
        
        print(f"✓ Сессия создана успешно")
        print(f"  ID сессии: {session_id}")
        print(f"  Токен аутентификации: {auth_token[:20]}...")
        
        # Очистка: удаляем сессию
        session.delete(f"{auth_url}/{session_id}")
    
    def test_02_system_info(self, session, base_url):
        """
        Тест получения информации о системе
        ○ Отправить GET-запрос на /redfish/v1/Systems/system.
        ○ Проверить статус-код (200).
        ○ Убедиться, что в JSON-ответе есть Status и PowerState.
        """
        print("\n=== Тест информации о системе ===")
        
        # Отправляем GET-запрос на /redfish/v1/Systems/system
        system_url = f"{base_url}/redfish/v1/Systems/system"
        response = session.get(system_url)
        
        # Проверяем статус-код (200)
        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"
        
        # Проверяем, что в JSON-ответе есть Status и PowerState
        system_data = response.json()
        
        assert 'Status' in system_data, "Поле Status отсутствует в ответе"
        assert 'PowerState' in system_data, "Поле PowerState отсутствует в ответе"
        
        # Дополнительные проверки структуры Status
        status = system_data['Status']
        assert 'Health' in status, "Поле Health отсутствует в Status"
        assert 'State' in status, "Поле State отсутствует в Status"
        
        # Выводим информацию о системе
        power_state = system_data['PowerState']
        health = status['Health']
        system_state = status['State']
        
        print(f"✓ Информация о системе получена успешно")
        print(f"  Состояние питания: {power_state}")
        print(f"  Здоровье системы: {health}")
        print(f"  Состояние системы: {system_state}")
        print(f"  Производитель: {system_data.get('Manufacturer', 'N/A')}")
        print(f"  Модель: {system_data.get('Model', 'N/A')}")
        
        # Сохраняем данные для использования в других тестах
        self.system_data = system_data
    
    def test_03_power_management_on(self, session, base_url):
        """ Тест управления питанием (включение сервера)
        ○ Отправить POST-запрос на /redfish/v1/Systems/system/Actions/ComputerSystem.Reset 
        с параметром "ResetType": "On".
        ○ Проверить, что ответ содержит 202 Accepted ИЛИ 204 No Content.
        ○ Убедиться, что статус системы изменился на "PowerState": "On" после обновления информации.
        """
        print("\n=== Тест управления питанием (включение) ===")
        
        # Сначала получаем текущее состояние системы
        system_url = f"{base_url}/redfish/v1/Systems/system"
        system_response = session.get(system_url)
        assert system_response.status_code == 200
        
        initial_state = system_response.json().get('PowerState')
        print(f"Начальное состояние питания: {initial_state}")
        
        # Если система уже включена, пропускаем тест включения
        if initial_state == "On":
            pytest.skip("Система уже включена, тест включения пропущен")
        
        # Отправляем POST-запрос для включения
        reset_url = f"{base_url}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
        reset_data = {
            "ResetType": "ForceOn"
        }
        
        response = session.post(reset_url, json=reset_data)
        
        # ИСПРАВЛЕНИЕ: принимаем как 202, так и 204 как валидные ответы
        assert response.status_code in [202, 204], (
            f"Ожидался статус 202 или 204, получен {response.status_code}. Ответ: {response.text}"
        )
        
        if response.status_code == 202:
            print("✓ Команда включения принята (202 Accepted)")
        else:
            print("✓ Команда включения выполнена (204 No Content)")
        
        # Ждем некоторое время для применения изменений
        time.sleep(10)
        
        # Проверяем, что статус системы изменился на "PowerState": "On"
        max_retries = 10
        power_on_confirmed = False
        
        for attempt in range(max_retries):
            system_response = session.get(system_url)
            current_state = system_response.json().get('PowerState')
            
            if current_state == "On":
                power_on_confirmed = True
                print(f"✓ Система успешно включена (попытка {attempt + 1})")
                break
            else:
                print(f"  Попытка {attempt + 1}: система еще не включена. Текущее состояние: {current_state}")
                time.sleep(5)
        
        assert power_on_confirmed, f"Система не включилась в течение {max_retries * 5} секунд"
    
    def test_04_power_management_off(self, session, base_url):
        """
        Тест управления питанием (выключение сервера)
        """
        print("\n=== Тест управления питанием (выключение) ===")
        
        # Сначала получаем текущее состояние системы
        system_url = f"{base_url}/redfish/v1/Systems/system"
        system_response = session.get(system_url)
        assert system_response.status_code == 200
        
        initial_state = system_response.json().get('PowerState')
        print(f"Начальное состояние питания: {initial_state}")
        
        # Если система уже выключена, пропускаем тест выключения
        if initial_state == "Off":
            pytest.skip("Система уже выключена, тест выключения пропущен")
        
        # Отправляем POST-запрос для выключения
        reset_url = f"{base_url}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
        reset_data = {
            "ResetType": "ForceOff"
        }
        
        response = session.post(reset_url, json=reset_data)
        
        # ИСПРАВЛЕНИЕ: принимаем как 202, так и 204 как валидные ответы
        assert response.status_code in [202, 204], (
            f"Ожидался статус 202 или 204, получен {response.status_code}. Ответ: {response.text}"
        )
        
        if response.status_code == 202:
            print("✓ Команда выключения принята (202 Accepted)")
        else:
            print("✓ Команда выключения выполнена (204 No Content)")
        
        # Ждем некоторое время для применения изменений
        time.sleep(10)
        
        # Проверяем, что статус системы изменился на "PowerState": "Off"
        max_retries = 8
        power_off_confirmed = False
        
        for attempt in range(max_retries):
            system_response = session.get(system_url)
            current_state = system_response.json().get('PowerState')
            
            if current_state == "Off":
                power_off_confirmed = True
                print(f"✓ Система успешно выключена (попытка {attempt + 1})")
                break
            else:
                print(f"  Попытка {attempt + 1}: система еще не выключена. Текущее состояние: {current_state}")
                time.sleep(5)
        
        assert power_off_confirmed, f"Система не выключилась в течение {max_retries * 5} секунд"
    
    def test_05_cpu_temperature_normal_range(self, session, base_url):
        """
        Тест на соответствие температуры CPU норме в Redfish
        ○ Необходимо разработать тест в соответствии документации Redfish
        """
        print("\n=== Тест температуры CPU ===")
        
        # Получаем информацию о температурных датчиках
        thermal_url = f"{base_url}/redfish/v1/Chassis/chassis/ThermalSubsystem/ThermalMetrics"
        response = session.get(thermal_url)
        
        # Если endpoint не существует, пробуем альтернативный путь
        if response.status_code == 404:
            thermal_url = f"{base_url}/redfish/v1/Chassis/chassis/ThermalSubsystem/ThermalMetrics"
            response = session.get(thermal_url)
        
        assert response.status_code == 200, f"Не удалось получить thermal data: {response.status_code}. URL: {thermal_url}"
        
        thermal_data = response.json()
        assert 'Temperatures' in thermal_data, pytest.skip("Датчики температуры CPU не найдены")
        
        print(f"Найдено датчиков температуры: {len(thermal_data['Temperatures'])}")
        
        # Ищем CPU temperature sensors
        cpu_temperatures = []
        for sensor in thermal_data['Temperatures']:
            sensor_name = sensor.get('Name', '').lower()
            sensor_physical_context = sensor.get('PhysicalContext', '').lower()
            
            # Ищем датчики, связанные с CPU/процессором
            if any(cpu_keyword in sensor_name or cpu_keyword in sensor_physical_context 
                   for cpu_keyword in ['cpu', 'processor', 'core', 'dimm']):
                cpu_temperatures.append(sensor)
        
        assert len(cpu_temperatures) > 0, "Датчики температуры CPU не найдены"
        
        
        print(f"Найдено датчиков CPU: {len(cpu_temperatures)}")
        
        # Проверяем температуру CPU
        all_temps_normal = True
        for cpu_sensor in cpu_temperatures:
            temperature = cpu_sensor.get('ReadingCelsius')
            sensor_name = cpu_sensor.get('Name', 'Unknown')
            physical_context = cpu_sensor.get('PhysicalContext', 'Unknown')
            
            assert temperature is not None, f"Температура не указана для датчика {sensor_name}"
            
            # Определяем нормальный диапазон в зависимости от типа датчика
            if 'cpu' in sensor_name.lower() or 'processor' in sensor_name.lower():
                min_temp, max_temp = 10, 95
            elif 'dimm' in sensor_name.lower() or 'memory' in sensor_name.lower():
                min_temp, max_temp = 15, 85
            else:
                min_temp, max_temp = 10, 80
            
            # Проверяем, что температура в нормальном диапазоне
            is_normal = min_temp <= temperature <= max_temp
            status_icon = "✓" if is_normal else "✗"
            
            if not is_normal:
                all_temps_normal = False
            
            # Проверяем наличие пороговых значений
            upper_critical = cpu_sensor.get('UpperThresholdCritical', 'N/A')
            upper_fatal = cpu_sensor.get('UpperThresholdFatal', 'N/A')
            
            print(f"  {status_icon} {sensor_name} ({physical_context}): {temperature}°C "
                  f"[норма: {min_temp}-{max_temp}°C] "
                  f"(критично: {upper_critical}°C, фатально: {upper_fatal}°C)")
            
            # Проверяем статус датчика
            status = cpu_sensor.get('Status', {})
            if 'Health' in status:
                health = status['Health']
                if health != 'OK':
                    print(f"    ВНИМАНИЕ: статус здоровья датчика: {health}")
        
        assert all_temps_normal, "Один или несколько датчиков CPU имеют температуру вне нормального диапазона"
        print("✓ Все датчики CPU в нормальном диапазоне температур")
    
    def test_06_temperature_sensor_structure(self, session, base_url):
        """
        Проверка структуры температурных датчиков согласно Redfish стандарту
        """
        print("\n=== Тест структуры датчиков температуры ===")
        
        # Получаем информацию о температурных датчиках
        thermal_url = f"{base_url}/redfish/v1/Chassis/chassis/Thermal"
        response = session.get(thermal_url)
        
        # Если endpoint не существует, пробуем альтернативный путь
        if response.status_code == 404:
            thermal_url = f"{base_url}/redfish/v1/Chassis/1/Thermal"
            response = session.get(thermal_url)
        
        if response.status_code != 200:
            pytest.skip(f"Не удалось получить thermal data: {response.status_code}")
        
        thermal_data = response.json()
        
        # Базовые обязательные поля согласно Redfish стандарту
        required_thermal_fields = ['@odata.id', 'Temperatures']
        for field in required_thermal_fields:
            assert field in thermal_data, f"Обязательное поле {field} отсутствует в Thermal"
        
        print("✓ Базовая структура Thermal соответствует Redfish стандарту")
        
        # Проверяем структуру каждого температурного датчика
        required_sensor_fields = [
            '@odata.id', 'Name', 'ReadingCelsius', 
            'UpperThresholdCritical', 'Status'
        ]
        
        recommended_sensor_fields = [
            'PhysicalContext', 'SensorNumber', 'MinReadingRange', 
            'MaxReadingRange', 'UpperThresholdFatal'
        ]
        
        sensors_checked = 0
        for sensor in thermal_data.get('Temperatures', []):
            sensors_checked += 1
            
            # Проверяем обязательные поля
            for field in required_sensor_fields:
                assert field in sensor, f"Обязательное поле {field} отсутствует в датчике {sensor.get('Name', 'Unknown')}"
            
            # Проверяем рекомендуемые поля
            missing_recommended = [field for field in recommended_sensor_fields if field not in sensor]
            if missing_recommended:
                print(f"  Предупреждение: датчик {sensor['Name']} не имеет полей: {', '.join(missing_recommended)}")
            
            # Проверяем структуру Status
            status = sensor['Status']
            assert 'Health' in status, f"Поле Health отсутствует в Status датчика {sensor['Name']}"
            assert 'State' in status, f"Поле State отсутствует в Status датчика {sensor['Name']}"
        
        print(f"✓ Проверена структура {sensors_checked} датчиков температуры")
        
        # Проверяем, что все датчики имеют статус Health = OK
        healthy_sensors = 0
        for sensor in thermal_data.get('Temperatures', []):
            status = sensor.get('Status', {})
            if status.get('Health') == 'OK':
                healthy_sensors += 1
        
        print(f"✓ Датчиков в состоянии 'OK': {healthy_sensors} из {sensors_checked}")
    
    def test_07_cpu_sensors_redfish_vs_ipmi(self, session, base_url):
        """
        Тест на соответствие датчиков CPU в Redfish и IPMI
        ○ Необходимо разработать тест в соответствии документации Redfish и IPMI
        """
        print("\n=== Тест сравнения Redfish и IPMI ===")
        
        def parse_ipmi_sensors():
            """
            Парсит вывод IPMI sensors и извлекает температуру CPU
            """
            try:
                # Запускаем ipmitool для получения информации о датчиках
                result = subprocess.run(
                    ['ipmitool', 'sensor', 'list'],
                    capture_output=True, 
                    text=True, 
                    check=True,
                    timeout=30
                )
                
                cpu_temperatures = {}
                lines = result.stdout.split('\n')
                
                for line in lines:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in ['temp', 'cpu', 'core', 'dimm']):
                        # Парсим строку вида "CPU Temp      | 45.000     | degrees C"
                        parts = re.split(r'\s*\|\s*', line)
                        if len(parts) >= 3:
                            sensor_name = parts[0].strip()
                            temperature_str = parts[1].strip()
                            units = parts[2].strip()
                            
                            # Извлекаем числовое значение температуры
                            temp_match = re.search(r'(\d+\.?\d*)', temperature_str)
                            if temp_match and ('c' in units.lower() or 'degrees c' in units.lower()):
                                temp_value = float(temp_match.group(1))
                                cpu_temperatures[sensor_name] = temp_value
                
                return cpu_temperatures
                
            except subprocess.CalledProcessError as e:
                pytest.skip(f"IPMI tool не доступен: {e}")
            except FileNotFoundError:
                pytest.skip("IPMI tool не установлен")
            except subprocess.TimeoutExpired:
                pytest.skip("IPMI tool timeout")
        
        # Получаем температуру из Redfish
        thermal_url = f"{base_url}/redfish/v1/Chassis/chassis/Thermal"
        response = session.get(thermal_url)
        
        # Если endpoint не существует, пробуем альтернативный путь
        if response.status_code == 404:
            thermal_url = f"{base_url}/redfish/v1/Chassis/1/Thermal"
            response = session.get(thermal_url)
        
        if response.status_code != 200:
            pytest.skip(f"Не удалось получить thermal data из Redfish: {response.status_code}")
        
        thermal_data = response.json()
        
        redfish_temps = {}
        for sensor in thermal_data.get('Temperatures', []):
            sensor_name = sensor.get('Name', '')
            temp = sensor.get('ReadingCelsius')
            if temp is not None:
                redfish_temps[sensor_name] = temp
        
        if not redfish_temps:
            pytest.skip("Не найдено датчиков температуры в Redfish")
        
        print(f"Датчики Redfish: {list(redfish_temps.keys())}")
        
        # Получаем температуру из IPMI
        ipmi_temps = parse_ipmi_sensors()
        
        if not ipmi_temps:
            pytest.skip("Не найдено датчиков температуры в IPMI")
        
        print(f"Датчики IPMI: {list(ipmi_temps.keys())}")
        
        # Сравниваем показания (допускаем разницу в 5°C из-за задержек измерений)
        tolerance = 5.0
        compared_sensors = 0
        matching_sensors = 0
        
        print("\nСравнение показаний:")
        print("-" * 60)
        
        for redfish_sensor, redfish_temp in redfish_temps.items():
            # Ищем соответствующий датчик в IPMI
            best_match = None
            best_match_name = None
            best_similarity = 0
            
            for ipmi_sensor, ipmi_temp in ipmi_temps.items():
                # Вычисляем схожесть имен датчиков
                similarity = self._calculate_similarity(redfish_sensor.lower(), ipmi_sensor.lower())
                if similarity > best_similarity and similarity > 0.3:  # Порог схожести
                    best_similarity = similarity
                    best_match = ipmi_temp
                    best_match_name = ipmi_sensor
            
            if best_match is not None:
                compared_sensors += 1
                difference = abs(redfish_temp - best_match)
                
                if difference <= tolerance:
                    matching_sensors += 1
                    status = "✓ СОВПАДАЕТ"
                else:
                    status = "✗ РАСХОЖДЕНИЕ"
                
                print(f"  {redfish_sensor:30} | Redfish: {redfish_temp:6.1f}°C | "
                      f"IPMI: {best_match:6.1f}°C | Разница: {difference:5.1f}°C | {status}")
        
        print("-" * 60)
        
        if compared_sensors == 0:
            pytest.skip("Не удалось сопоставить датчики между Redfish и IPMI")
        
        match_percentage = (matching_sensors / compared_sensors) * 100
        print(f"Результат: {matching_sensors}/{compared_sensors} датчиков совпадают ({match_percentage:.1f}%)")
        
        # Тест считается пройденным если хотя бы 70% датчиков совпадают
        assert match_percentage >= 70, f"Менее 70% датчиков совпадают между Redfish и IPMI"
        
        print("✓ Показания Redfish и IPMI в основном совпадают")
    
    def _calculate_similarity(self, str1, str2):
        """Вычисляет схожесть между двумя строками"""
        # Простой алгоритм схожести - можно улучшить
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0
        
        common_words = words1.intersection(words2)
        similarity = len(common_words) / max(len(words1), len(words2))
        return similarity
    
    def test_08_redfish_service_root(self, session, base_url):
        """
        Дополнительный тест: проверка корневого endpoint Redfish
        """
        print("\n=== Тест корневого endpoint Redfish ===")
        
        response = session.get(f"{base_url}/redfish/v1/")
        assert response.status_code == 200, f"Корневой endpoint недоступен: {response.status_code}"
        
        service_root = response.json()
        
        # Проверяем обязательные поля согласно Redfish стандарту
        required_fields = ['@odata.id', 'Id', 'Name', 'RedfishVersion']
        for field in required_fields:
            assert field in service_root, f"Обязательное поле {field} отсутствует в Service Root"
        
        # Проверяем основные endpoints
        expected_endpoints = ['Systems', 'Chassis', 'Managers', 'SessionService']
        available_endpoints = 0
        
        print("Доступные endpoints:")
        for endpoint in expected_endpoints:
            if endpoint in service_root:
                available_endpoints += 1
                endpoint_url = service_root[endpoint]['@odata.id']
                print(f"  ✓ {endpoint}: {endpoint_url}")
            else:
                print(f"  ✗ {endpoint}: отсутствует")
        
        assert available_endpoints >= 2, f"Слишком мало endpoints доступно: {available_endpoints}"
        
        print(f"✓ Корневой endpoint Redfish корректен, доступно {available_endpoints}/4 основных endpoints")
