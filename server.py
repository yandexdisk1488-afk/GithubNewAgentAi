#!/usr/bin/env python3
"""
🚀 Advanced Multi-User AI Chat Server
Полнофункциональный сервер с поддержкой неограниченных пользователей и чатов
"""

import os
import sys
import json
import uuid
import logging
import threading
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chat_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== ENUMS ====================
class ChatStatus(Enum):
    """Статус чата"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class UserRole(Enum):
    """Роль пользователя"""
    USER = "user"
    ADMIN = "admin"
    GUEST = "guest"


# ==================== DATA MODELS ====================
@dataclass
class Message:
    """Модель сообщения"""
    id: str
    user_id: str
    chat_id: str
    role: str  # "user" или "assistant"
    content: str
    timestamp: datetime
    tokens: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tokens": self.tokens
        }


@dataclass
class Chat:
    """Модель чата"""
    id: str
    user_id: str
    title: str
    model: str
    status: ChatStatus
    created_at: datetime
    updated_at: datetime
    messages: List[Message] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    total_tokens: int = 0
    
    def to_dict(self, include_messages: bool = True) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "model": self.model,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [m.to_dict() for m in self.messages] if include_messages else [],
            "total_messages": len(self.messages),
            "total_tokens": self.total_tokens
        }


@dataclass
class User:
    """Модель пользователя"""
    id: str
    username: str
    email: str
    created_at: datetime
    last_login: datetime
    role: UserRole
    is_active: bool = True
    max_chats: int = 100
    max_tokens_per_day: int = 100000
    settings: Dict[str, Any] = field(default_factory=dict)
    chats_count: int = 0
    total_tokens_used: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat(),
            "role": self.role.value,
            "is_active": self.is_active,
            "max_chats": self.max_chats,
            "chats_count": self.chats_count,
            "total_tokens_used": self.total_tokens_used
        }


# ==================== DATABASE ====================
class ChatDatabase:
    """Управление базой данных"""
    
    def __init__(self, db_path: str = "chat_data.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализировать базу данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    max_chats INTEGER DEFAULT 100,
                    max_tokens_per_day INTEGER DEFAULT 100000,
                    total_tokens_used INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}'
                )
            ''')
            
            # Таблица чатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT DEFAULT 'gpt-3.5-turbo',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_tokens INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokens INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            conn.commit()
            logger.info("✅ База данных инициализирована")
    
    def create_user(self, username: str, email: str, role: UserRole = UserRole.USER) -> User:
        """Создать пользователя"""
        user_id = str(uuid.uuid4())
        now = datetime.now()
        
        user = User(
            id=user_id,
            username=username,
            email=email,
            created_at=now,
            last_login=now,
            role=role
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (id, username, email, role, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user.id, user.username, user.email, user.role.value, user.created_at, user.last_login))
            conn.commit()
        
        logger.info(f"✅ Пользователь создан: {username}")
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Получить пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
        
        if row:
            return self._row_to_user(row)
        return None
    
    def create_chat(self, user_id: str, title: str, model: str = "gpt-3.5-turbo") -> Chat:
        """Создать новый чат"""
        chat_id = str(uuid.uuid4())
        now = datetime.now()
        
        chat = Chat(
            id=chat_id,
            user_id=user_id,
            title=title or f"Chat {now.strftime('%Y-%m-%d %H:%M')}",
            model=model,
            status=ChatStatus.ACTIVE,
            created_at=now,
            updated_at=now
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chats (id, user_id, title, model, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (chat.id, chat.user_id, chat.title, chat.model, 
                  chat.status.value, chat.created_at, chat.updated_at))
            conn.commit()
        
        logger.info(f"✅ Чат создан: {chat_id}")
        return chat
    
    def get_chat(self, chat_id: str) -> Optional[Chat]:
        """Получить чат с сообщениями"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM chats WHERE id = ?', (chat_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            chat = self._row_to_chat(row)
            
            # Загрузить сообщения
            cursor.execute('''
                SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp ASC
            ''', (chat_id,))
            
            for msg_row in cursor.fetchall():
                message = self._row_to_message(msg_row)
                chat.messages.append(message)
            
            return chat
    
    def add_message(self, chat_id: str, user_id: str, role: str, content: str, tokens: int = 0) -> Message:
        """Добавить сообщение"""
        message_id = str(uuid.uuid4())
        now = datetime.now()
        
        message = Message(
            id=message_id,
            user_id=user_id,
            chat_id=chat_id,
            role=role,
            content=content,
            timestamp=now,
            tokens=tokens
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Добавить сообщение
            cursor.execute('''
                INSERT INTO messages (id, chat_id, user_id, role, content, tokens, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message.id, message.chat_id, message.user_id, message.role, 
                  message.content, message.tokens, message.timestamp))
            
            # Обновить время чата
            cursor.execute('''
                UPDATE chats SET updated_at = ? WHERE id = ?
            ''', (now, chat_id))
            
            # Обновить токены
            cursor.execute('''
                UPDATE chats SET total_tokens = total_tokens + ? WHERE id = ?
            ''', (tokens, chat_id))
            
            cursor.execute('''
                UPDATE users SET total_tokens_used = total_tokens_used + ? WHERE id = ?
            ''', (tokens, user_id))
            
            conn.commit()
        
        return message
    
    def get_user_chats(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Chat]:
        """Получить чаты пользователя"""
        chats = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))
            
            for row in cursor.fetchall():
                chats.append(self._row_to_chat(row))
        
        return chats
    
    def _row_to_user(self, row) -> User:
        """Преобразовать строку в User"""
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            role=UserRole(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            last_login=datetime.fromisoformat(row[5]) if row[5] else None,
            is_active=bool(row[6]),
            max_chats=row[7],
            max_tokens_per_day=row[8],
            total_tokens_used=row[9],
            settings=json.loads(row[10]) if row[10] else {}
        )
    
    def _row_to_chat(self, row) -> Chat:
        """Преобразовать строку в Chat"""
        return Chat(
            id=row[0],
            user_id=row[1],
            title=row[2],
            model=row[3],
            status=ChatStatus(row[4]),
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            total_tokens=row[7],
            settings=json.loads(row[8]) if row[8] else {}
        )
    
    def _row_to_message(self, row) -> Message:
        """Преобразовать строку в Message"""
        return Message(
            id=row[0],
            chat_id=row[1],
            user_id=row[2],
            role=row[3],
            content=row[4],
            tokens=row[5],
            timestamp=datetime.fromisoformat(row[6])
        )


# ==================== LLM SERVICE ====================
class LLMService:
    """Сервис для работы с LLM"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.default_model = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")
        self.use_local = os.getenv("USE_LOCAL_MODEL", "false").lower() == "true"
    
    def chat(self, messages: List[Dict[str, str]], model: str = None, temperature: float = 0.7) -> Tuple[str, int]:
        """Отправить сообщения в LLM"""
        model = model or self.default_model
        
        if self.use_local:
            return self._ollama_chat(messages, model, temperature)
        else:
            return self._openai_chat(messages, model, temperature)
    
    def _openai_chat(self, messages: List[Dict[str, str]], model: str, temperature: float) -> Tuple[str, int]:
        """Чат с OpenAI"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens
            
            return content, tokens
            
        except Exception as e:
            logger.error(f"❌ OpenAI ошибка: {e}")
            return f"Ошибка: {str(e)}", 0
    
    def _ollama_chat(self, messages: List[Dict[str, str]], model: str, temperature: float) -> Tuple[str, int]:
        """Чат с Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=300
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get('message', {}).get('content', '')
                # Ollama не возвращает токены, оцениваем примерно
                tokens = len(content.split()) * 1.3
                return content, int(tokens)
            else:
                return f"Ошибка Ollama: {response.status_code}", 0
                
        except Exception as e:
            logger.error(f"❌ Ollama ошибка: {e}")
            return f"Ошибка: {str(e)}", 0


# ==================== FLASK APP ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
CORS(app)

# Initialize services
db = ChatDatabase()
llm = LLMService()

logger.info("🚀 AI Chat Server инициализирован")


# ==================== ROUTES ====================
@app.route('/', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "service": "AI Chat Server",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/users/register', methods=['POST'])
def register_user():
    """Регистрация пользователя"""
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        
        if not username or not email:
            return jsonify({"error": "Username и email обязательны"}), 400
        
        user = db.create_user(username, email)
        session['user_id'] = user.id
        
        return jsonify({
            "success": True,
            "user": user.to_dict(),
            "message": f"Пользователь {username} успешно создан"
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/login', methods=['POST'])
def login_user():
    """Вход пользователя"""
    try:
        data = request.json
        username = data.get('username')
        
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
        
        if row:
            user_id = row[0]
            session['user_id'] = user_id
            user = db.get_user(user_id)
            return jsonify({"success": True, "user": user.to_dict()})
        else:
            return jsonify({"error": "Пользователь не найден"}), 404
            
    except Exception as e:
        logger.error(f"❌ Ошибка входа: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/chats/create', methods=['POST'])
def create_chat():
    """Создать новый чат"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Не авторизован"}), 401
        
        data = request.json
        title = data.get('title', '')
        model = data.get('model', llm.default_model)
        
        chat = db.create_chat(user_id, title, model)
        
        return jsonify({
            "success": True,
            "chat": chat.to_dict(include_messages=False),
            "message": f"Чат создан: {chat.id}"
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания чата: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Получить чат"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Не авторизован"}), 401
        
        chat = db.get_chat(chat_id)
        if not chat or chat.user_id != user_id:
            return jsonify({"error": "Чат не найден"}), 404
        
        return jsonify({
            "success": True,
            "chat": chat.to_dict()
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения чата: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/chats', methods=['GET'])
def list_chats():
    """Получить список чатов пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Не авторизован"}), 401
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        chats = db.get_user_chats(user_id, limit, offset)
        
        return jsonify({
            "success": True,
            "chats": [c.to_dict(include_messages=False) for c in chats],
            "total": len(chats)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/chats/<chat_id>/messages', methods=['POST'])
def send_message(chat_id):
    """Отправить сообщение в чат"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Не авторизован"}), 401
        
        data = request.json
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        
        # Получить чат
        chat = db.get_chat(chat_id)
        if not chat or chat.user_id != user_id:
            return jsonify({"error": "Чат не найден"}), 404
        
        # Добавить сообщение пользователя
        user_msg = db.add_message(chat_id, user_id, "user", content)
        
        # Подготовить историю для LLM
        messages = []
        for msg in chat.messages:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": content})
        
        # Получить ответ от LLM
        response_text, tokens = llm.chat(messages, chat.model)
        
        # Добавить ответ ассистента
        assistant_msg = db.add_message(chat_id, user_id, "assistant", response_text, tokens)
        
        return jsonify({
            "success": True,
            "user_message": user_msg.to_dict(),
            "assistant_message": assistant_msg.to_dict(),
            "chat_id": chat_id
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Получить статистику"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Не авторизован"}), 401
        
        user = db.get_user(user_id)
        chats = db.get_user_chats(user_id)
        
        return jsonify({
            "success": True,
            "user": user.to_dict(),
            "stats": {
                "total_chats": len(chats),
                "total_tokens_used": user.total_tokens_used,
                "chats": [c.to_dict(include_messages=False) for c in chats]
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint не найден"}), 404


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ==================== MAIN ====================
def main():
    """Главная функция"""
    print("""
╔═══════════════════════════════════════════════════════╗
║   🚀 ADVANCED AI CHAT SERVER - MULTI USER             ║
║   Каждый пользователь = неограниченные чаты            ║
║   Каждый чат = отдельный контекст                     ║
╚═══════════════════════════════════════════════════════╝

✨ Особенности:
   ✅ Регистрация и авторизация
   ✅ Неограниченные чаты per пользователя
   ✅ Сохранение истории сообщений
   ✅ Поддержка OpenAI и Ollama
   ✅ Учет токенов
   ✅ REST API
   ✅ SQLite база данных

📡 API Endpoints:
   POST   /api/users/register          - Создать пользователя
   POST   /api/users/login             - Вход
   POST   /api/chats/create            - Новый чат
   GET    /api/chats                   - Список чатов
   GET    /api/chats/<chat_id>         - Получить чат
   POST   /api/chats/<chat_id>/messages - Отправить сообщение
   GET    /api/stats                   - Статистика

🔧 Конфигурация:
   OPENAI_API_KEY      - API ключ OpenAI
   OLLAMA_URL          - URL Ollama (http://localhost:11434)
   DEFAULT_MODEL       - Модель по умолчанию
   USE_LOCAL_MODEL     - Использовать локальную модель (true/false)
    """)
    
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🚀 Сервер запускается на 0.0.0.0:{port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
