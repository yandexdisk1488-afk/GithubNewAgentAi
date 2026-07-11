#!/usr/bin/env python3
"""
🚀 ChatGPT GUI Application
Полнофункциональное приложение для чата с GPT с красивым интерфейсом
Все компоненты встроены в один файл - готово к запуску как SFX архив

Автоматическая установка зависимостей при первом запуске!
"""

import sys
import os
import json
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import traceback

# ==================== AUTO INSTALL DEPENDENCIES ====================
def ensure_dependencies():
    """Автоматическая установка всех необходимых зависимостей"""
    required_packages = {
        'PyQt6': 'PyQt6',
        'openai': 'openai>=1.3.0',
        'python-dotenv': 'python-dotenv>=1.0.0',
        'requests': 'requests>=2.31.0',
    }
    
    missing = []
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"📦 Установка зависимостей: {', '.join(missing)}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q'] + missing)
        print("✅ Зависимости установлены!")

ensure_dependencies()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QSlider, QSpinBox,
    QFileDialog, QMessageBox, QTabWidget, QScrollArea, QSplitter,
    QSystemTrayIcon, QMenu, QStatusBar, QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPalette, QKeySequence
from PyQt6.QtWidgets import QApplication as QApp

from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv


# ==================== CONFIGURATION ====================
class Config:
    """Конфигурация приложения"""
    
    # UI Constants
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    FONT_SIZE = 10
    CHAT_FONT_SIZE = 11
    
    # Colors (Dark Theme)
    DARK_BG = "#1a1a1a"
    DARK_INPUT = "#2d2d2d"
    DARK_TEXT = "#ffffff"
    ACCENT_COLOR = "#00a8ff"
    
    # Models
    AVAILABLE_MODELS = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k"
    ]
    
    # Default settings
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MODEL = "gpt-3.5-turbo"
    MAX_TOKENS = 4096
    
    # Paths
    CONFIG_DIR = Path.home() / ".chatgpt_gui"
    ENV_FILE = CONFIG_DIR / ".env"
    HISTORY_FILE = CONFIG_DIR / "chat_history.json"
    SETTINGS_FILE = CONFIG_DIR / "settings.json"


# ==================== OPENAI CLIENT MANAGER ====================
class OpenAIManager:
    """Менеджер для работы с OpenAI API"""
    
    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.model = Config.DEFAULT_MODEL
        self.temperature = Config.DEFAULT_TEMPERATURE
        self.conversation_history = []
        self.initialize()
    
    def initialize(self):
        """Инициализировать клиент OpenAI"""
        load_dotenv(Config.ENV_FILE)
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY не установлен!")
        
        self.client = OpenAI(api_key=api_key)
    
    def set_model(self, model: str):
        """Установить модель"""
        self.model = model
    
    def set_temperature(self, temp: float):
        """Установить температуру"""
        self.temperature = max(0.0, min(2.0, temp))
    
    def add_message(self, role: str, content: str):
        """Добавить сообщение в историю"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
    
    def clear_history(self):
        """Очистить историю"""
        self.conversation_history = []
    
    def get_response(self, user_message: str) -> str:
        """Получить ответ от GPT"""
        try:
            self.add_message("user", user_message)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                temperature=self.temperature,
                max_tokens=Config.MAX_TOKENS
            )
            
            assistant_message = response.choices[0].message.content
            self.add_message("assistant", assistant_message)
            
            return assistant_message
            
        except APIConnectionError as e:
            return f"❌ Ошибка подключения: {str(e)}"
        except RateLimitError:
            return f"⏱️ Ограничение по запросам. Попробуй позже."
        except APIError as e:
            return f"❌ Ошибка API: {str(e)}"
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"


# ==================== CHAT WORKER THREAD ====================
class ChatWorker(QThread):
    """Рабочий поток для обработки сообщений"""
    
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, manager: OpenAIManager, message: str):
        super().__init__()
        self.manager = manager
        self.message = message
    
    def run(self):
        """Запустить рабочий поток"""
        try:
            response = self.manager.get_response(self.message)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(f"❌ Ошибка: {str(e)}")


# ==================== MAIN APPLICATION ====================
class ChatGPTGUI(QMainWindow):
    """Главное окно приложения ChatGPT GUI"""
    
    def __init__(self):
        super().__init__()
        
        # Инициализация менеджера
        try:
            self.manager = OpenAIManager()
        except ValueError as e:
            self.show_error("❌ Ошибка инициализации", str(e))
            sys.exit(1)
        
        self.current_worker: Optional[ChatWorker] = None
        self.is_loading = False
        
        # Создание директорий
        Config.CONFIG_DIR.mkdir(exist_ok=True)
        
        # Инициализация UI
        self.init_ui()
        self.load_settings()
        self.load_history()
    
    def init_ui(self):
        """Инициализировать пользовательский интерфейс"""
        self.setWindowTitle("💬 ChatGPT GUI - Полнофункциональный чат")
        self.setGeometry(100, 100, Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setStyleSheet(self.get_stylesheet())
        
        # Создание центрального виджета
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # ====== ЛЕВАЯ ПАНЕЛЬ: ЧАТ ======
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("💬 Чат с GPT")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        left_layout.addWidget(title)
        
        # Область чата
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Consolas", Config.CHAT_FONT_SIZE))
        left_layout.addWidget(self.chat_display)
        
        # Поле ввода
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("Введи сообщение и нажми Shift+Enter для отправки...")
        self.chat_input.setMaximumHeight(100)
        self.chat_input.setFont(QFont("Consolas", Config.FONT_SIZE))
        left_layout.addWidget(self.chat_input)
        
        # Кнопки действий
        button_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("📤 Отправить")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(self.send_btn)
        
        self.clear_btn = QPushButton("🗑️ Очистить")
        self.clear_btn.clicked.connect(self.clear_chat)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(self.clear_btn)
        
        self.copy_btn = QPushButton("📋 Копировать")
        self.copy_btn.clicked.connect(self.copy_last_response)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(self.copy_btn)
        
        left_layout.addLayout(button_layout)
        
        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximum(0)
        left_layout.addWidget(self.progress)
        
        left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel, 2)
        
        # ====== ПРАВАЯ ПАНЕЛЬ: НАСТРОЙКИ ======
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Заголовок
        settings_title = QLabel("⚙️ Настройки")
        settings_title.setFont(title_font)
        right_layout.addWidget(settings_title)
        
        # Модель
        right_layout.addWidget(QLabel("🤖 Модель:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(Config.AVAILABLE_MODELS)
        self.model_combo.setCurrentText(Config.DEFAULT_MODEL)
        self.model_combo.currentTextChanged.connect(
            lambda: self.manager.set_model(self.model_combo.currentText())
        )
        right_layout.addWidget(self.model_combo)
        
        # Температура
        right_layout.addWidget(QLabel("🌡️ Температура:"))
        temp_layout = QHBoxLayout()
        
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setMinimum(0)
        self.temp_slider.setMaximum(200)
        self.temp_slider.setValue(int(Config.DEFAULT_TEMPERATURE * 100))
        self.temp_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.temp_slider.setTickInterval(10)
        self.temp_slider.sliderMoved.connect(self.on_temperature_changed)
        temp_layout.addWidget(self.temp_slider)
        
        self.temp_label = QLabel(f"{Config.DEFAULT_TEMPERATURE:.1f}")
        self.temp_label.setMinimumWidth(40)
        temp_layout.addWidget(self.temp_label)
        
        right_layout.addLayout(temp_layout)
        
        # Макс токены
        right_layout.addWidget(QLabel("📝 Макс токены:"))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setMinimum(100)
        self.tokens_spin.setMaximum(8192)
        self.tokens_spin.setValue(Config.MAX_TOKENS)
        self.tokens_spin.setSingleStep(100)
        right_layout.addWidget(self.tokens_spin)
        
        # Разделитель
        right_layout.addSpacing(20)
        
        # История
        right_layout.addWidget(QLabel("📚 История"))
        
        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setMaximumHeight(200)
        self.history_display.setFont(QFont("Consolas", 8))
        right_layout.addWidget(self.history_display)
        
        # Кнопки истории
        history_btn_layout = QHBoxLayout()
        
        save_history_btn = QPushButton("💾 Сохранить")
        save_history_btn.clicked.connect(self.save_chat_history)
        history_btn_layout.addWidget(save_history_btn)
        
        load_history_btn = QPushButton("📂 Загрузить")
        load_history_btn.clicked.connect(self.load_chat_history)
        history_btn_layout.addWidget(load_history_btn)
        
        right_layout.addLayout(history_btn_layout)
        
        # Разделитель
        right_layout.addSpacing(20)
        
        # Информация
        right_layout.addWidget(QLabel("ℹ️ Информация"))
        
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.update_info_label()
        right_layout.addWidget(self.info_label)
        
        # Растягивающееся пространство
        right_layout.addStretch()
        
        # Кнопка настроек API
        settings_btn = QPushButton("🔑 API Ключ")
        settings_btn.clicked.connect(self.setup_api_key)
        right_layout.addWidget(settings_btn)
        
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel, 1)
        
        # Status bar
        self.statusBar().showMessage("✅ Готово")
        
        # Горячие клавиши
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Настроить горячие клавиши"""
        from PyQt6.QtGui import QShortcut
        
        # Shift+Enter для отправки сообщения
        QShortcut(QKeySequence("Shift+Return"), self.send_message, context=Qt.ShortcutContext.WidgetShortcut)
        QShortcut(QKeySequence("Shift+Enter"), self.send_message, context=Qt.ShortcutContext.WidgetShortcut)
    
    def send_message(self):
        """Отправить сообщение"""
        message = self.chat_input.toPlainText().strip()
        
        if not message:
            self.show_warning("⚠️ Пустое сообщение", "Пожалуйста введи сообщение")
            return
        
        if self.is_loading:
            self.show_warning("⏳ Подожди", "Предыдущее сообщение еще обрабатывается")
            return
        
        # Добавить сообщение пользователя в чат
        self.display_message("👤 Ты", message, "#00a8ff")
        self.chat_input.clear()
        
        # Показать индикатор загрузки
        self.is_loading = True
        self.progress.setVisible(True)
        self.send_btn.setEnabled(False)
        self.statusBar().showMessage("⏳ Ожидание ответа...")
        
        # Запустить рабочий поток
        self.current_worker = ChatWorker(self.manager, message)
        self.current_worker.response_received.connect(self.on_response_received)
        self.current_worker.error_occurred.connect(self.on_error)
        self.current_worker.start()
    
    def on_response_received(self, response: str):
        """Обработать полученный ответ"""
        self.display_message("🤖 GPT", response, "#00ff88")
        self.is_loading = False
        self.progress.setVisible(False)
        self.send_btn.setEnabled(True)
        self.statusBar().showMessage("✅ Готово")
        self.update_info_label()
    
    def on_error(self, error_msg: str):
        """Обработать ошибку"""
        self.display_message("❌ Ошибка", error_msg, "#ff4444")
        self.is_loading = False
        self.progress.setVisible(False)
        self.send_btn.setEnabled(True)
        self.statusBar().showMessage("❌ Ошибка")
    
    def display_message(self, role: str, content: str, color: str):
        """Отобразить сообщение в чате"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f"""
        <div style="margin: 10px 0; padding: 8px; background-color: #2d2d2d; border-radius: 5px;">
            <span style="color: {color}; font-weight: bold;">{role}</span>
            <span style="color: #888; font-size: 0.8em;"> [{timestamp}]</span>
            <div style="color: #ffffff; margin-top: 5px; word-wrap: break-word;">
                {content.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')}
            </div>
        </div>
        """
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(html)
        self.chat_display.ensureCursorVisible()
    
    def clear_chat(self):
        """Очистить чат"""
        reply = QMessageBox.question(
            self, "Очистить чат?", "Это удалит всю историю сообщений. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.chat_display.clear()
            self.manager.clear_history()
            self.statusBar().showMessage("✅ Чат очищен")
            self.update_info_label()
    
    def copy_last_response(self):
        """Копировать последний ответ"""
        try:
            from PyQt6.QtGui import QClipboard
            clipboard = QApplication.clipboard()
            text = self.chat_display.toPlainText()
            clipboard.setText(text)
            self.statusBar().showMessage("✅ Скопировано в буфер обмена")
        except Exception as e:
            self.show_error("❌ Ошибка копирования", str(e))
    
    def on_temperature_changed(self):
        """Обработать изменение температуры"""
        temp = self.temp_slider.value() / 100.0
        self.temp_label.setText(f"{temp:.1f}")
        self.manager.set_temperature(temp)
    
    def save_chat_history(self):
        """Сохранить историю чата"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить историю", "", "JSON Files (*.json);;Text Files (*.txt)"
            )
            
            if file_path:
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.manager.conversation_history, f, ensure_ascii=False, indent=2)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        for msg in self.manager.conversation_history:
                            f.write(f"{msg['role'].upper()}:\n{msg['content']}\n\n")
                
                self.statusBar().showMessage(f"✅ История сохранена: {file_path}")
        except Exception as e:
            self.show_error("❌ Ошибка сохранения", str(e))
    
    def load_chat_history(self):
        """Загрузить историю чата"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Загрузить историю", "", "JSON Files (*.json)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    self.manager.conversation_history = history
                    self.chat_display.clear()
                    
                    for msg in history:
                        role = "👤 Ты" if msg['role'] == 'user' else "🤖 GPT"
                        color = "#00a8ff" if msg['role'] == 'user' else "#00ff88"
                        self.display_message(role, msg['content'], color)
                
                self.statusBar().showMessage(f"✅ История загружена: {file_path}")
                self.update_info_label()
        except Exception as e:
            self.show_error("❌ Ошибка загрузки", str(e))
    
    def load_history(self):
        """Загрузить последнюю историю"""
        try:
            if Config.HISTORY_FILE.exists():
                with open(Config.HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.manager.conversation_history = json.load(f)
        except:
            pass
    
    def save_settings(self):
        """Сохранить настройки"""
        try:
            settings = {
                'model': self.model_combo.currentText(),
                'temperature': self.temp_slider.value() / 100.0,
                'max_tokens': self.tokens_spin.value()
            }
            
            with open(Config.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except:
            pass
    
    def load_settings(self):
        """Загрузить настройки"""
        try:
            if Config.SETTINGS_FILE.exists():
                with open(Config.SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    
                    model = settings.get('model', Config.DEFAULT_MODEL)
                    if model in Config.AVAILABLE_MODELS:
                        self.model_combo.setCurrentText(model)
                    
                    temp = settings.get('temperature', Config.DEFAULT_TEMPERATURE)
                    self.temp_slider.setValue(int(temp * 100))
                    
                    Config.MAX_TOKENS = settings.get('max_tokens', Config.MAX_TOKENS)
                    self.tokens_spin.setValue(Config.MAX_TOKENS)
        except:
            pass
    
    def update_info_label(self):
        """Обновить информацион метку"""
        history_len = len(self.manager.conversation_history)
        model = self.model_combo.currentText()
        temp = self.temp_slider.value() / 100.0
        
        info_text = f"""
        📊 Информация:
        • Модель: {model}
        • Температура: {temp:.1f}
        • Сообщений: {history_len}
        • Время: {datetime.now().strftime('%H:%M:%S')}
        """
        
        self.info_label.setText(info_text.strip())
    
    def setup_api_key(self):
        """Настроить API ключ"""
        from PyQt6.QtWidgets import QDialog, QLineEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔑 API Ключ OpenAI")
        dialog.setGeometry(400, 300, 500, 150)
        dialog.setStyleSheet(self.get_stylesheet())
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Введи свой OpenAI API ключ:"))
        
        key_input = QLineEdit()
        key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Загрузить текущий ключ
        current_key = os.getenv("OPENAI_API_KEY", "")
        if current_key:
            key_input.setText(current_key)
        
        layout.addWidget(key_input)
        
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        cancel_btn = QPushButton("❌ Отмена")
        
        def save_key():
            api_key = key_input.text().strip()
            if not api_key:
                QMessageBox.warning(dialog, "⚠️ Пусто", "Пожалуйста, введи API ключ")
                return
            
            try:
                # Сохранить в .env
                Config.ENV_FILE.parent.mkdir(exist_ok=True)
                with open(Config.ENV_FILE, 'w') as f:
                    f.write(f"OPENAI_API_KEY={api_key}\n")
                
                # Обновить переменную окружения
                os.environ["OPENAI_API_KEY"] = api_key
                
                # Пересоздать клиент
                self.manager = OpenAIManager()
                
                QMessageBox.information(dialog, "✅ Сохранено", "API ключ успешно сохранен!")
                dialog.close()
            except Exception as e:
                QMessageBox.critical(dialog, "❌ Ошибка", f"Ошибка сохранения: {str(e)}")
        
        save_btn.clicked.connect(save_key)
        cancel_btn.clicked.connect(dialog.close)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def show_error(self, title: str, message: str):
        """Показать ошибку"""
        QMessageBox.critical(self, title, message)
    
    def show_warning(self, title: str, message: str):
        """Показать предупреждение"""
        QMessageBox.warning(self, title, message)
    
    def closeEvent(self, event):
        """Обработать закрытие окна"""
        self.save_settings()
        
        try:
            with open(Config.HISTORY_FILE, 'w') as f:
                json.dump(self.manager.conversation_history, f, ensure_ascii=False, indent=2)
        except:
            pass
        
        event.accept()
    
    @staticmethod
    def get_stylesheet() -> str:
        """Получить таблицу стилей"""
        return f"""
        QMainWindow, QWidget {{
            background-color: {Config.DARK_BG};
            color: {Config.DARK_TEXT};
        }}
        
        QTextEdit {{
            background-color: {Config.DARK_INPUT};
            color: {Config.DARK_TEXT};
            border: 1px solid {Config.ACCENT_COLOR};
            border-radius: 5px;
            padding: 5px;
            font-size: {Config.FONT_SIZE}pt;
        }}
        
        QPushButton {{
            background-color: {Config.ACCENT_COLOR};
            color: {Config.DARK_BG};
            border: none;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
            font-size: {Config.FONT_SIZE}pt;
        }}
        
        QPushButton:hover {{
            background-color: #0086cc;
        }}
        
        QPushButton:pressed {{
            background-color: #0066aa;
        }}
        
        QPushButton:disabled {{
            background-color: #666;
            color: #999;
        }}
        
        QComboBox {{
            background-color: {Config.DARK_INPUT};
            color: {Config.DARK_TEXT};
            border: 1px solid {Config.ACCENT_COLOR};
            border-radius: 5px;
            padding: 5px;
            font-size: {Config.FONT_SIZE}pt;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {Config.DARK_INPUT};
            color: {Config.DARK_TEXT};
            selection-background-color: {Config.ACCENT_COLOR};
        }}
        
        QSlider::groove:horizontal {{
            background-color: {Config.DARK_INPUT};
            height: 8px;
            border-radius: 4px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {Config.ACCENT_COLOR};
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background-color: #0086cc;
        }}
        
        QSpinBox {{
            background-color: {Config.DARK_INPUT};
            color: {Config.DARK_TEXT};
            border: 1px solid {Config.ACCENT_COLOR};
            border-radius: 5px;
            padding: 5px;
            font-size: {Config.FONT_SIZE}pt;
        }}
        
        QLabel {{
            color: {Config.DARK_TEXT};
            font-size: {Config.FONT_SIZE}pt;
        }}
        
        QStatusBar {{
            background-color: {Config.DARK_INPUT};
            color: {Config.DARK_TEXT};
        }}
        
        QProgressBar {{
            background-color: {Config.DARK_INPUT};
            border: 1px solid {Config.ACCENT_COLOR};
            border-radius: 5px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {Config.ACCENT_COLOR};
        }}
        """


# ==================== MAIN ====================
def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Установить иконку приложения
    app.setApplicationName("ChatGPT GUI")
    app.setApplicationVersion("1.0.0")
    
    # Создать главное окно
    window = ChatGPTGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
