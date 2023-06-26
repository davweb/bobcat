from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

class Chrome(WebDriver):
    def __init__(self, options: Options, service: Service) -> None: ...
