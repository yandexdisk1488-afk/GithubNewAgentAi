#!/usr/bin/env python3
"""
🚀 Advanced Local LLM Server Integration
Профессиональная поддержка локальных LLM моделей с полным функционалом
"""

import os
import sys
import json
import time
import logging
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import threading
from queue import Queue


# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== ENUMS & CONFIGS ====================
class ModelProvider(Enum):
    """Поддерживаемые провайдеры моделей"""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    LM_STUDIO = "lm_studio"
    PRIVATE_GPT = "private_gpt"
    VLLM = "vllm"
    TEXT_GENERATION_WEBUI = "text_generation_webui"
    OPENAI = "openai"


class ModelStatus(Enum):
    """Статус модели"""
    AVAILABLE = "доступна"
    LOADING = "загружается"
    UNLOADING = "выгружается"
    NOT_FOUND = "не найдена"
    ERROR = "ошибка"


@dataclass
class ModelInfo:
    """Информация о модели"""
    name: str
    provider: ModelProvider
    size_gb: float = 0.0
    parameters: int = 0
    context_length: int = 4096
    quantization: str = "unknown"
    description: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ServerConfig:
    """Конфигурация локального сервера"""
    provider: ModelProvider
    host: str = "localhost"
    port: int = 11434
    timeout: int = 300
    max_retries: int = 3
    verify_ssl: bool = False
    api_key: Optional[str] = None
    
    @property
    def base_url(self) -> str:
        protocol = "https" if self.verify_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"
    
    def __str__(self) -> str:
        return f"{self.provider.value}://{self.host}:{self.port}"


# ==================== BASE CLIENT ====================
class BaseLocalClient(ABC):
    """Абстрактный базовый класс для клиентов"""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.session = self._create_session()
        self.available_models: List[ModelInfo] = []
        self.current_model: Optional[str] = None
        self.conversation_history: List[Dict[str, str]] = []
        self.is_connected = False
        self.stats = {
            "requests": 0,
            "errors": 0,
            "total_tokens": 0,
            "response_time": 0.0
        }
        logger.info(f"🔧 Инициализация {self.__class__.__name__} для {config}")
    
    def _create_session(self) -> requests.Session:
        """Создать сессию с повторными попытками"""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def test_connection(self) -> bool:
        """Проверить соединение с сервером"""
        try:
            response = self.session.get(
                self.config.base_url,
                timeout=5,
                verify=self.config.verify_ssl
            )
            self.is_connected = response.status_code == 200
            if self.is_connected:
                logger.info(f"✅ Подключено к {self.config}")
            return self.is_connected
        except Exception as e:
            logger.error(f"❌ Не удается подключиться к {self.config}: {e}")
            self.is_connected = False
            return False
    
    def clear_history(self) -> None:
        """Очистить историю разговора"""
        self.conversation_history = []
        logger.info("🧹 История очищена")
    
    def add_system_prompt(self, prompt: str) -> None:
        """Добавить системный промпт"""
        self.conversation_history.insert(0, {
            "role": "system",
            "content": prompt
        })
    
    @abstractmethod
    def load_available_models(self) -> List[ModelInfo]:
        """Загрузить доступные модели"""
        pass
    
    @abstractmethod
    def chat(self, user_message: str, temperature: float = 0.7) -> str:
        """Отправить сообщение и получить ответ"""
        pass
    
    @abstractmethod
    def stream_chat(self, user_message: str, temperature: float = 0.7):
        """Потоковый чат"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        return {
            "provider": self.config.provider.value,
            "connected": self.is_connected,
            "current_model": self.current_model,
            **self.stats
        }


# ==================== OLLAMA CLIENT ====================
class OllamaClient(BaseLocalClient):
    """Продвинутый клиент для Ollama"""
    
    def load_available_models(self) -> List[ModelInfo]:
        """Загрузить доступные модели из Ollama"""
        try:
            response = self.session.get(
                f"{self.config.base_url}/api/tags",
                timeout=10,
                verify=self.config.verify_ssl
            )
            
            if response.status_code == 200:
                data = response.json()
                self.available_models = []
                
                for model in data.get('models', []):
                    model_info = ModelInfo(
                        name=model['name'],
                        provider=ModelProvider.OLLAMA,
                        size_gb=model.get('size', 0) / (1024**3),
                        parameters=model.get('parameters', 0),
                        description=model.get('details', {}).get('family', 'Unknown')
                    )
                    self.available_models.append(model_info)
                
                logger.info(f"✅ Загружено {len(self.available_models)} моделей")
                return self.available_models
            else:
                logger.error(f"❌ Ошибка загрузки моделей: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке моделей: {e}")
            return []
    
    def set_model(self, model_name: str) -> bool:
        """Установить текущую модель"""
        if any(m.name == model_name for m in self.available_models):
            self.current_model = model_name
            logger.info(f"📌 Модель установлена: {model_name}")
            return True
        logger.error(f"❌ Модель не найдена: {model_name}")
        return False
    
    def chat(self, user_message: str, temperature: float = 0.7) -> str:
        """Чат с Ollama"""
        if not self.current_model:
            logger.error("❌ Модель не установлена")
            return "❌ Ошибка: модель не установлена"
        
        try:
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            start_time = time.time()
            
            payload = {
                "model": self.current_model,
                "messages": self.conversation_history,
                "temperature": temperature,
                "stream": False
            }
            
            response = self.session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            
            elapsed_time = time.time() - start_time
            self.stats["response_time"] = elapsed_time
            self.stats["requests"] += 1
            
            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {}).get('content', '')
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": message
                })
                
                logger.info(f"✅ Ответ получен за {elapsed_time:.2f}s")
                return message
            else:
                self.stats["errors"] += 1
                error_msg = f"❌ Ошибка сервера: {response.status_code}"
                logger.error(error_msg)
                return error_msg
                
        except requests.exceptions.Timeout:
            self.stats["errors"] += 1
            error_msg = "❌ Истекло время ожидания"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            self.stats["errors"] += 1
            error_msg = f"❌ Ошибка: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def stream_chat(self, user_message: str, temperature: float = 0.7):
        """Потоковый чат"""
        if not self.current_model:
            yield "❌ Модель не установлена"
            return
        
        try:
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            payload = {
                "model": self.current_model,
                "messages": self.conversation_history,
                "temperature": temperature,
                "stream": True
            }
            
            response = self.session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                full_message = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        chunk = data.get('message', {}).get('content', '')
                        full_message += chunk
                        yield chunk
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_message
                })
            else:
                yield f"❌ Ошибка: {response.status_code}"
                
        except Exception as e:
            yield f"❌ Ошибка: {str(e)}"
    
    def pull_model(self, model_name: str, callback: Optional[Callable] = None) -> bool:
        """Загрузить модель"""
        try:
            logger.info(f"📥 Загрузка модели: {model_name}")
            
            response = self.session.post(
                f"{self.config.base_url}/api/pull",
                json={"name": model_name},
                timeout=3600,
                verify=self.config.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line and callback:
                        data = json.loads(line)
                        status = data.get('status', '')
                        if callback:
                            callback(status)
                
                self.load_available_models()
                logger.info(f"✅ Модель загружена: {model_name}")
                return True
            else:
                logger.error(f"❌ Ошибка загрузки: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """Удалить модель"""
        try:
            response = self.session.delete(
                f"{self.config.base_url}/api/delete",
                json={"name": model_name},
                timeout=30,
                verify=self.config.verify_ssl
            )
            
            if response.status_code == 200:
                self.load_available_models()
                logger.info(f"✅ Модель удалена: {model_name}")
                return True
            else:
                logger.error(f"❌ Ошибка удаления: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Получить подробную информацию о модели"""
        try:
            response = self.session.post(
                f"{self.config.base_url}/api/show",
                json={"name": model_name},
                timeout=10,
                verify=self.config.verify_ssl
            )
            
            if response.status_code == 200:
                return response.json()
            return {}
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return {}


# ==================== LLAMA.CPP CLIENT ====================
class LlamaCppClient(BaseLocalClient):
    """Клиент для llama.cpp"""
    
    def load_available_models(self) -> List[ModelInfo]:
        """Загрузить информацию о текущей модели"""
        try:
            model_info = ModelInfo(
                name="llama.cpp",
                provider=ModelProvider.LLAMA_CPP,
                description="GGUF модель в llama.cpp"
            )
            self.available_models = [model_info]
            self.current_model = "llama.cpp"
            logger.info("✅ llama.cpp готов")
            return self.available_models
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return []
    
    def chat(self, user_message: str, temperature: float = 0.7) -> str:
        """Чат с llama.cpp"""
        try:
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            start_time = time.time()
            
            payload = {
                "messages": self.conversation_history,
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
                "max_tokens": 2048
            }
            
            response = self.session.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            
            elapsed_time = time.time() - start_time
            self.stats["response_time"] = elapsed_time
            self.stats["requests"] += 1
            
            if response.status_code == 200:
                data = response.json()
                message = data['choices'][0]['message']['content']
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": message
                })
                
                logger.info(f"✅ Ответ получен за {elapsed_time:.2f}s")
                return message
            else:
                self.stats["errors"] += 1
                return f"❌ Ошибка: {response.status_code}"
                
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ Ошибка: {e}")
            return f"❌ Ошибка: {str(e)}"
    
    def stream_chat(self, user_message: str, temperature: float = 0.7):
        """Потоковый чат"""
        try:
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            payload = {
                "messages": self.conversation_history,
                "temperature": temperature,
                "stream": True,
                "max_tokens": 2048
            }
            
            response = self.session.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                stream=True
            )
            
            full_message = ""
            for line in response.iter_lines():
                if line and b'data:' in line:
                    data_str = line.decode().replace('data: ', '').strip()
                    if data_str and data_str != '[DONE]':
                        data = json.loads(data_str)
                        chunk = data['choices'][0]['delta'].get('content', '')
                        full_message += chunk
                        yield chunk
            
            self.conversation_history.append({
                "role": "assistant",
                "content": full_message
            })
            
        except Exception as e:
            yield f"❌ Ошибка: {str(e)}"


# ==================== LM STUDIO CLIENT ====================
class LMStudioClient(LlamaCppClient):
    """Клиент для LM Studio (совместим с llama.cpp API)"""
    
    def __init__(self, config: ServerConfig):
        if config.port == 11434:
            config.port = 1234
        super().__init__(config)
        logger.info("🎨 LM Studio клиент инициализирован")


# ==================== MULTI-PROVIDER MANAGER ====================
class LocalLLMManager:
    """Менеджер для управления несколькими провайдерами"""
    
    def __init__(self):
        self.clients: Dict[ModelProvider, BaseLocalClient] = {}
        self.current_provider: Optional[ModelProvider] = None
        logger.info("🎛️ Менеджер LLM инициализирован")
    
    def add_provider(self, config: ServerConfig) -> bool:
        """Добавить провайдера"""
        try:
            if config.provider == ModelProvider.OLLAMA:
                client = OllamaClient(config)
            elif config.provider == ModelProvider.LLAMA_CPP:
                client = LlamaCppClient(config)
            elif config.provider == ModelProvider.LM_STUDIO:
                client = LMStudioClient(config)
            else:
                logger.error(f"❌ Неизвестный провайдер: {config.provider}")
                return False
            
            if client.test_connection():
                client.load_available_models()
                self.clients[config.provider] = client
                logger.info(f"✅ Добавлен {config.provider.value}")
                return True
            else:
                logger.error(f"❌ Не удается подключиться к {config.provider.value}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении провайдера: {e}")
            return False
    
    def switch_provider(self, provider: ModelProvider) -> bool:
        """Переключиться на другого провайдера"""
        if provider in self.clients:
            self.current_provider = provider
            logger.info(f"🔄 Переключено на {provider.value}")
            return True
        logger.error(f"❌ Провайдер не доступен: {provider.value}")
        return False
    
    def get_current_client(self) -> Optional[BaseLocalClient]:
        """Получить текущего клиента"""
        if self.current_provider and self.current_provider in self.clients:
            return self.clients[self.current_provider]
        return None
    
    def list_all_models(self) -> Dict[str, List[ModelInfo]]:
        """Список всех моделей от всех провайдеров"""
        result = {}
        for provider, client in self.clients.items():
            result[provider.value] = client.available_models
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику от всех провайдеров"""
        return {
            provider.value: client.get_stats()
            for provider, client in self.clients.items()
        }


if __name__ == "__main__":
    print("✅ Модуль локальных LLM готов к использованию")
