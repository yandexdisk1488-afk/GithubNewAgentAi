#!/usr/bin/env python3
"""
AI Agent on OpenAI API
Простой и мощный агент для взаимодействия с ChatGPT
"""

import os
import sys
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class AIAgent:
    """Класс для управления AI агентом"""
    
    def __init__(self, model: str = "gpt-3.5-turbo", temperature: float = 0.7):
        """
        Инициализация агента
        
        Args:
            model: Модель OpenAI для использования
            temperature: Температура для генерации (0-2, где 0 - детерминированно)
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY не установлен в .env файле!")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.conversation_history = []
        self.system_prompt = """Ты полезный AI ассистент. Отвечай на русском языке.
Будь дружелюбным, информативным и точным в своих ответах."""
    
    def set_system_prompt(self, prompt: str) -> None:
        """Установить системный промпт для агента"""
        self.system_prompt = prompt
    
    def clear_history(self) -> None:
        """Очистить историю разговора"""
        self.conversation_history = []
        print("✨ История разговора очищена")
    
    def chat(self, user_message: str) -> str:
        """
        Отправить сообщение агенту и получить ответ
        
        Args:
            user_message: Сообщение от пользователя
            
        Returns:
            Ответ от AI агента
        """
        # Добавляем сообщение в историю
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Формируем сообщения с системным промптом
            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.conversation_history
            ]
            
            # Отправляем запрос в OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            
            # Извлекаем ответ
            assistant_message = response.choices[0].message.content
            
            # Добавляем ответ в историю
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            error_msg = f"❌ Ошибка при запросе к OpenAI: {str(e)}"
            print(error_msg)
            return error_msg
    
    def get_conversation_length(self) -> int:
        """Получить количество сообщений в истории"""
        return len(self.conversation_history)


def print_welcome():
    """Вывести приветственное сообщение"""
    print("\n" + "="*60)
    print("🤖 AI AGENT ON OPENAI API")
    print("="*60)
    print("Команды:")
    print("  'exit' или 'quit'     - Выход")
    print("  'clear' или 'reset'   - Очистить историю")
    print("  'history'             - Показать историю разговора")
    print("  'help'                - Справка")
    print("="*60 + "\n")


def main():
    """Главная функция"""
    try:
        # Инициализируем агента
        agent = AIAgent(model="gpt-3.5-turbo", temperature=0.7)
        print_welcome()
        
        print("✅ Агент успешно запущен!\n")
        
        # Основной цикл
        while True:
            try:
                user_input = input("👤 Ты: ").strip()
                
                # Проверяем команды
                if user_input.lower() in ['exit', 'quit']:
                    print("\n👋 До свидания! Спасибо за использование AI Agent.")
                    break
                
                elif user_input.lower() in ['clear', 'reset']:
                    agent.clear_history()
                    continue
                
                elif user_input.lower() == 'history':
                    if agent.conversation_history:
                        print("\n📝 История разговора:")
                        print("-" * 60)
                        for msg in agent.conversation_history:
                            role = "👤 Ты" if msg["role"] == "user" else "🤖 Агент"
                            print(f"{role}: {msg['content'][:100]}...")
                        print("-" * 60)
                        print(f"Всего сообщений: {agent.get_conversation_length()}\n")
                    else:
                        print("📝 История пуста\n")
                    continue
                
                elif user_input.lower() == 'help':
                    print_welcome()
                    continue
                
                elif not user_input:
                    continue
                
                # Получаем ответ от агента
                print("\n⏳ Агент думает...\n")
                response = agent.chat(user_input)
                print(f"🤖 Агент: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Прервано пользователем")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}\n")
    
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
