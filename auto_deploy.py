#!/usr/bin/env python3
"""
🚀 Automatic Free AI Server Deployer
Автоматическое развертывание AI сервера на бесплатных хостингах
"""

import os
import sys
import json
import subprocess
import time
import logging
from typing import Optional, Dict, List, Tuple
from enum import Enum
import requests
from dataclasses import dataclass
import threading
from datetime import datetime

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_deploy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== ENUMS ====================
class FreeHost(Enum):
    """Поддерживаемые бесплатные хостинги"""
    REPLIT = "replit"
    HEROKU = "heroku"
    RENDER = "render"
    RAILWAY = "railway"
    VERCEL = "vercel"
    HUGGINGFACE_SPACES = "huggingface_spaces"
    PYTHONANYWHERE = "pythonanywhere"
    GLITCH = "glitch"


@dataclass
class DeploymentConfig:
    """Конфиг развертывания"""
    host: FreeHost
    model_name: str = "mistral"
    api_port: int = 8000
    app_name: str = "ai-agent-server"
    region: str = "us"
    timeout: int = 300


# ==================== BASE DEPLOYER ====================
class BaseDeployer:
    """Базовый класс для развертывания"""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.server_url: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        logger.info(f"🔧 Инициализация {self.__class__.__name__}")
    
    def check_requirements(self) -> bool:
        """Проверить требования"""
        return True
    
    def setup_environment(self) -> bool:
        """Настроить окружение"""
        return True
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть сервер"""
        raise NotImplementedError
    
    def test_connection(self) -> bool:
        """Проверить соединение"""
        if not self.server_url:
            return False
        try:
            response = requests.get(self.server_url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def stop(self) -> bool:
        """Остановить сервер"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                self.is_running = False
                logger.info("✅ Сервер остановлен")
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")
                return False
        return False


# ==================== REPLIT DEPLOYER ====================
class ReplitDeployer(BaseDeployer):
    """Развертывание на Replit"""
    
    def check_requirements(self) -> bool:
        """Проверить требования для Replit"""
        # Проверяем переменные окружения Replit
        return 'REPLIT_HOME' in os.environ
    
    def setup_environment(self) -> bool:
        """Настроить окружение Replit"""
        try:
            # Создаем структуру проекта
            os.makedirs('.replit-env', exist_ok=True)
            
            # Создаем replit.nix
            replit_nix = '''
{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.git
  ];
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.libc
    ];
  };
}
'''
            with open('replit.nix', 'w') as f:
                f.write(replit_nix)
            
            logger.info("✅ Окружение Replit настроено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при настройке: {e}")
            return False
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть на Replit"""
        try:
            logger.info("📤 Развертывание на Replit...")
            
            # Устанавливаем зависимости
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                         check=True, capture_output=True)
            
            # Создаем главный сервер-скрипт
            server_code = self._generate_server_code()
            with open('server.py', 'w') as f:
                f.write(server_code)
            
            # Запускаем сервер
            self.process = subprocess.Popen(
                [sys.executable, "server.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            time.sleep(3)
            
            # Получаем URL Replit
            replit_domain = os.environ.get('REPLIT_SLUG', 'local')
            self.server_url = f"https://{replit_domain}.repl.co"
            
            if self.process.poll() is None:
                self.is_running = True
                logger.info(f"✅ Развернуто на {self.server_url}")
                return True, self.server_url
            else:
                return False, "Ошибка запуска сервера"
                
        except Exception as e:
            logger.error(f"❌ Ошибка развертывания: {e}")
            return False, str(e)
    
    def _generate_server_code(self) -> str:
        """Генерировать код сервера"""
        return '''
import os
from flask import Flask, request, jsonify
import requests
import threading

app = Flask(__name__)

# Конфиг
OLLAMA_URL = "http://localhost:11434"
MODEL = "mistral"

@app.route('/')
def health():
    return jsonify({"status": "ok", "model": MODEL})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        messages = data.get('messages', [])
        
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=300
        )
        
        if response.status_code == 200:
            return response.json()
        return jsonify({"error": "Error from Ollama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/models', methods=['GET'])
def list_models():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags")
        if response.status_code == 200:
            return response.json()
        return jsonify({"models": []})
    except:
        return jsonify({"models": []})

def start_ollama():
    """Запустить Ollama в фоновом потоке"""
    os.system(f"ollama serve --port 11434 &")

if __name__ == '__main__':
    # Запускаем Ollama
    threading.Thread(target=start_ollama, daemon=True).start()
    time.sleep(5)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
'''


# ==================== HUGGINGFACE SPACES DEPLOYER ====================
class HuggingFaceSpacesDeployer(BaseDeployer):
    """Развертывание на Hugging Face Spaces"""
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть на Hugging Face Spaces"""
        try:
            logger.info("📤 Подготовка к развертыванию на Hugging Face Spaces...")
            
            # Создаем файл app.py для Gradio
            app_code = self._generate_gradio_app()
            with open('app.py', 'w') as f:
                f.write(app_code)
            
            # Создаем requirements.txt
            requirements = "gradio\nrequests\npython-dotenv\n"
            with open('requirements.txt', 'a') as f:
                if 'gradio' not in f.read():
                    f.write(requirements)
            
            # Инструкции по развертыванию
            instructions = f"""
✅ Для развертывания на Hugging Face Spaces:

1. Перейдите на https://huggingface.co/spaces
2. Создайте новый Space
3. Выберите "Docker" как Space SDK
4. Загрузите текущий репозиторий
5. Space автоматически развернется на URL:
   https://huggingface.co/spaces/YOUR_USERNAME/{self.config.app_name}

Текущие файлы готовы к развертыванию!
"""
            logger.info(instructions)
            return True, "https://huggingface.co/spaces"
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False, str(e)
    
    def _generate_gradio_app(self) -> str:
        """Генерировать Gradio приложение"""
        return '''
import gradio as gr
import requests
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MODEL", "mistral")

def chat(message, history):
    """Chat function for Gradio"""
    try:
        # Готовим историю для Ollama
        messages = []
        for msg, response in history:
            messages.append({"role": "user", "content": msg})
            messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": message})
        
        # Запрос к Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=300
        )
        
        if response.status_code == 200:
            return response.json()['message']['content']
        return "Ошибка при получении ответа"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# Создаем интерфейс
with gr.Blocks() as demo:
    gr.Markdown("# 🤖 AI Chat Agent")
    gr.Markdown(f"Модель: {MODEL}")
    
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="Сообщение")
    clear = gr.ClearButton([msg, chatbot])
    
    msg.submit(chat, [msg, chatbot], chatbot)

demo.launch(share=True)
'''


# ==================== RAILWAY DEPLOYER ====================
class RailwayDeployer(BaseDeployer):
    """Развертывание на Railway"""
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть на Railway"""
        try:
            logger.info("📤 Подготовка к развертыванию на Railway...")
            
            # Создаем Dockerfile
            dockerfile = '''FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "server.py"]
'''
            with open('Dockerfile', 'w') as f:
                f.write(dockerfile)
            
            # Создаем railway.json
            railway_config = {
                "name": self.config.app_name,
                "services": [
                    {
                        "name": "api",
                        "runtime": "dockerfile",
                        "envVariables": {
                            "PORT": "8000",
                            "MODEL": self.config.model_name
                        }
                    }
                ]
            }
            
            with open('railway.json', 'w') as f:
                json.dump(railway_config, f, indent=2)
            
            logger.info("""
✅ Dockerfile создан. Для развертывания:

1. Установите Railway CLI: npm install -g @railway/cli
2. Выполните: railway up
3. Ваше приложение развернется на Railway
""")
            return True, "https://railway.app"
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False, str(e)


# ==================== RENDER DEPLOYER ====================
class RenderDeployer(BaseDeployer):
    """Развертывание на Render"""
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть на Render"""
        try:
            logger.info("📤 Подготовка к развертыванию на Render...")
            
            # Создаем render.yaml
            render_config = f"""
services:
  - type: web
    name: {self.config.app_name}
    runtime: python
    runtimeVersion: 3.10
    buildCommand: pip install -r requirements.txt
    startCommand: python server.py
    envVars:
      - key: PORT
        value: 8000
      - key: MODEL
        value: {self.config.model_name}
"""
            with open('render.yaml', 'w') as f:
                f.write(render_config)
            
            logger.info("""
✅ render.yaml создан. Для развертывания:

1. Перейдите на https://render.com
2. Создайте новый Web Service
3. Подключите ваш GitHub репозиторий
4. Используйте render.yaml для конфигурации
5. Запустите deployment
""")
            return True, "https://render.com"
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False, str(e)


# ==================== PYTHONANYWHERE DEPLOYER ====================
class PythonAnywhereDeployer(BaseDeployer):
    """Развертывание на PythonAnywhere"""
    
    def deploy(self) -> Tuple[bool, str]:
        """Развернуть на PythonAnywhere"""
        try:
            logger.info("📤 Подготовка к развертыванию на PythonAnywhere...")
            
            # Создаем WSGI конфиг
            wsgi_code = '''
import sys
import os

path = '/home/YOUR_USERNAME/mysite'
if path not in sys.path:
    sys.path.append(path)

os.chdir(path)

from server import app
application = app
'''
            
            logger.info("""
✅ WSGI конфиг готов. Для развертывания:

1. Зарегистрируйтесь на https://www.pythonanywhere.com
2. Загрузите файлы вашего проекта
3. Создайте новый Web App
4. Используйте сгенерированный WSGI конфиг
5. Загрузите requirements.txt через Web App консоль
""")
            return True, "https://www.pythonanywhere.com"
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False, str(e)


# ==================== DEPLOYMENT MANAGER ====================
class AutoDeploymentManager:
    """Менеджер автоматического развертывания"""
    
    def __init__(self):
        self.deployers: Dict[FreeHost, BaseDeployer] = {}
        self.current_deployment: Optional[Tuple[FreeHost, str]] = None
        logger.info("🎛️ Менеджер развертывания инициализирован")
    
    def create_deployer(self, config: DeploymentConfig) -> bool:
        """Создать deployer для указанного хоста"""
        try:
            if config.host == FreeHost.REPLIT:
                deployer = ReplitDeployer(config)
            elif config.host == FreeHost.HUGGINGFACE_SPACES:
                deployer = HuggingFaceSpacesDeployer(config)
            elif config.host == FreeHost.RAILWAY:
                deployer = RailwayDeployer(config)
            elif config.host == FreeHost.RENDER:
                deployer = RenderDeployer(config)
            elif config.host == FreeHost.PYTHONANYWHERE:
                deployer = PythonAnywhereDeployer(config)
            else:
                logger.error(f"❌ Неизвестный хост: {config.host}")
                return False
            
            if deployer.check_requirements():
                deployer.setup_environment()
                self.deployers[config.host] = deployer
                logger.info(f"✅ Deployer создан для {config.host.value}")
                return True
            else:
                logger.error(f"❌ Требования не выполнены для {config.host.value}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при создании deployer: {e}")
            return False
    
    def deploy(self, config: DeploymentConfig) -> Tuple[bool, str]:
        """Развернуть приложение"""
        if not self.create_deployer(config):
            return False, f"Не удалось создать deployer для {config.host.value}"
        
        deployer = self.deployers[config.host]
        success, url = deployer.deploy()
        
        if success:
            self.current_deployment = (config.host, url)
            logger.info(f"🎉 Развертывание успешно! URL: {url}")
        
        return success, url
    
    def list_deployment_guides(self) -> str:
        """Получить руководства по развертыванию"""
        guides = """
╔════════════════════════════════════════════════════════════╗
║           🚀 БЕСПЛАТНЫЕ ХОСТИНГИ ДЛЯ AI СЕРВЕРА           ║
╚════════════════════════════════════════════════════════════╝

📌 REPLIT (Рекомендуется для новичков)
   ✅ Бесплатная машина с 1GB памяти
   ✅ Автоматический deploy с GitHub
   ✅ Встроенный IDE
   📊 Лимит: 1 проект
   🔗 https://replit.com

📌 HUGGING FACE SPACES (Лучше для ML)
   ✅ Бесплатный GPU (T4)
   ✅ Встроенный Gradio
   ✅ Коммьюнити поддержка
   📊 Лимит: 3 месяца неактивности
   🔗 https://huggingface.co/spaces

📌 RAILWAY (Лучше для API)
   ✅ $5 месячный кредит
   ✅ Быстрый deploy
   ✅ Переменные окружения
   📊 Нужна платежная карта
   🔗 https://railway.app

📌 RENDER (Альтернатива Railway)
   ✅ Бесплатный tier с спящим режимом
   ✅ HTTPS по умолчанию
   ✅ GitHub интеграция
   📊 Засыпает после 15 минут неактивности
   🔗 https://render.com

📌 PYTHONANYWHERE (Для Python)
   ✅ 512MB памяти бесплатно
   ✅ Встроенная консоль
   ✅ SQLite поддержка
   📊 Лимит: только localhost
   🔗 https://www.pythonanywhere.com

╔════════════════════════════════════════════════════════════╗
║                    🎯 СРАВНЕНИЕ                            ║
╚════════════════════════════════════════════════════════════╝

              |Память|GPU|Время|Цена|Легкость
Replit        | 1GB  | ❌ | ∞   | 0$ |   ⭐⭐⭐⭐⭐
HF Spaces     | 16GB | ✅ | 3mo | 0$ |   ⭐⭐⭐⭐
Railway       | 512MB| ❌ | ∞   | 5$ |   ⭐⭐⭐⭐
Render        | 512MB| ❌ | 15m | 0$ |   ⭐⭐⭐
PythonAnywhere| 512MB| ❌ | ∞   | 0$ |   ⭐⭐⭐
"""
        return guides


def main():
    """Главная функция"""
    print("""
╔═══════════════════════════════════════════════════════╗
║  🚀 AI AGENT - AUTOMATIC FREE SERVER DEPLOYER        ║
╚═══════════════════════════════════════════════════════╝
""")
    
    manager = AutoDeploymentManager()
    print(manager.list_deployment_guides())
    
    # Меню выбора
    print("\n📋 Доступные хостинги:")
    hosts = list(FreeHost)
    for i, host in enumerate(hosts, 1):
        print(f"  {i}. {host.value}")
    
    choice = input("\n👉 Выберите хостинг (номер): ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(hosts):
            selected_host = hosts[idx]
            config = DeploymentConfig(host=selected_host)
            
            success, url = manager.deploy(config)
            
            if success:
                print(f"\n✅ Успешно развернуто!")
                print(f"   Хостинг: {selected_host.value}")
                print(f"   URL: {url}")
            else:
                print(f"\n❌ Ошибка развертывания: {url}")
        else:
            print("❌ Неверный выбор")
    except ValueError:
        print("❌ Пожалуйста, введите номер")


if __name__ == "__main__":
    main()
