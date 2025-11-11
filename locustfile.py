from locust import HttpUser, task, between
import json

class OpenBMCUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://localhost:2443"
    
    def on_start(self):
        self.auth = ("root", "0penBmc") 
        
    @task(3)
    def get_system_info(self):
        with self.client.get("/redfish/v1/Systems/system", 
                           auth=self.auth,
                           catch_response=True,
                           name="Get System Info") as response:
            if response.status_code == 200:
                try:
                    system_data = response.json()
                    # Проверяем наличие необходимых полей
                    if 'Id' in system_data and 'Name' in system_data:
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(2)
    def get_power_state(self):
        with self.client.get("/redfish/v1/Systems/system", 
                           auth=self.auth,
                           catch_response=True,
                           name="Get Power State") as response:
            if response.status_code == 200:
                try:
                    system_data = response.json()
                    power_state = system_data.get('PowerState')
                    if power_state in ['On', 'Off']:
                        response.success()
                    else:
                        response.failure(f"Invalid power state: {power_state}")
                except (json.JSONDecodeError, AttributeError):
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code: {response.status_code}")

class PublicAPIUser(HttpUser):
    wait_time = between(1, 5)
    host = "https://jsonplaceholder.typicode.com"
    
    @task(4)
    def get_posts(self):
        with self.client.get("/posts", 
                           catch_response=True,
                           name="Get Posts List") as response:
            if response.status_code == 200:
                try:
                    posts = response.json()
                    if isinstance(posts, list) and len(posts) > 0:
                        response.success()
                    else:
                        response.failure("Empty or invalid posts list")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_weather(self):
        with self.client.get("https://wttr.in/Novosibirsk?format=j1", 
                           catch_response=True,
                           name="Get Weather Data") as response:
            if response.status_code == 200:
                try:
                    weather_data = response.json()
                    if 'current_condition' in weather_data:
                        response.success()
                    else:
                        response.failure("Invalid weather data format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status code: {response.status_code}")