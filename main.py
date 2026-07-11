#!/usr/bin/env python3
"""
🚀 Quick Start & Setup Guide
Быстрый запуск всех компонентов проекта
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def install_requirements():
    """Установить все зависимости"""
    print("📦 Установка зависимостей...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Зависимости установлены")


def create_env_file():
    """Создать .env файл"""
    if not os.path.exists(".env"):
        print("📝 Создание .env файла...")
        with open(".env", "w") as f:
            f.write("""# OpenAI Configuration
OPENAI_API_KEY=your_api_key_here

# Local LLM Configuration
USE_LOCAL_MODEL=false
OLLAMA_URL=http://localhost:11434
DEFAULT_MODEL=gpt-3.5-turbo

# Flask Configuration
FLASK_DEBUG=false
SECRET_KEY=your-secret-key-change-this
PORT=8000
""")
        print("✅ .env файл создан. Отредактируйте его с вашими ключами!")
    else:
        print("ℹ️  .env файл уже существует")


def start_simple_chat():
    """Запустить простой чат"""
    print("\n🎯 Запуск AI Chat Agent...")
    subprocess.run([sys.executable, "ai_agent.py"])


def start_server():
    """Запустить многопользовательский сервер"""
    print("\n🎯 Запуск Multi-User Chat Server...")
    subprocess.run([sys.executable, "server.py"])


def start_deployment():
    """Запустить систему развертывания"""
    print("\n🎯 Запуск Auto Deployment System...")
    subprocess.run([sys.executable, "auto_deploy.py"])


def show_menu():
    """Показать главное меню"""
    print("""
╔═════════════════════════════════════════════════════╗
║  🚀 AI AGENT SYSTEM - ГЛАВНОЕ МЕНЮ                 ║
║     Все компоненты в одном месте                   ║
╚═════════════════════════════════════════════════════╝

Выберите опцию:
  1️⃣  Простой чат (AI Agent)
  2️⃣  Многопользовательский сервер
  3️⃣  Система развертывания на бесплатные хостинги
  4️⃣  Локальные LLM модели
  5️⃣  Установить зависимости
  6️⃣  Создать .env файл
  0️⃣  Выход

""")


def main():
    """Главная функция"""
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8+")
        sys.exit(1)
    
    # Проверяем .env
    if not os.path.exists(".env"):
        create_env_file()
    
    while True:
        show_menu()
        choice = input("👉 Выберите опцию (0-6): ").strip()
        
        try:
            if choice == "1":
                start_simple_chat()
            elif choice == "2":
                start_server()
            elif choice == "3":
                start_deployment()
            elif choice == "4":
                print("💡 Для использования локальных моделей:")
                print("   1. Установите Ollama: https://ollama.ai")
                print("   2. Запустите: ollama serve")
                print("   3. Загрузите модель: ollama pull mistral")
                print("   4. Установите USE_LOCAL_MODEL=true в .env")
            elif choice == "5":
                install_requirements()
            elif choice == "6":
                create_env_file()
            elif choice == "0":
                print("👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор")
        except KeyboardInterrupt:
            print("\n⚠️ Отменено пользователем")
        except Exception as e:
            print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
