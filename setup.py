#!/usr/bin/env python3
"""
Setup script for Telegram RAG Chatbot
This script helps initialize the database and verify all dependencies
"""

import os
import sys
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.9 or higher"""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_env_file():
    """Check if .env file exists"""
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("   Please copy .env.example to .env and add your API keys")
        return False
    print("✅ .env file found")
    return True

def check_env_variables():
    """Check if required environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'GROQ_API_KEY',
        'GEMINI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith('your_'):
            missing_vars.append(var)
            print(f"❌ {var} not set or using default value")
        else:
            print(f"✅ {var} is configured")
    
    if missing_vars:
        print("\n⚠️  Missing API keys:")
        print("   TELEGRAM_BOT_TOKEN: Get from @BotFather on Telegram")
        print("   GROQ_API_KEY: Get from https://console.groq.com")
        print("   GEMINI_API_KEY: Get from https://makersuite.google.com/app/apikey")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = ['data', 'data/images', 'data/voice', 'data/vectordb']
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    return True

def initialize_database():
    """Initialize the database"""
    try:
        from database import init_db
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

def test_imports():
    """Test if all required packages can be imported"""
    required_packages = [
        ('telegram', 'python-telegram-bot'),
        ('langchain', 'langchain'),
        ('groq', 'groq'),
        ('google.generativeai', 'google-generativeai'),
        ('chromadb', 'chromadb'),
        ('sentence_transformers', 'sentence-transformers'),
        ('sqlalchemy', 'sqlalchemy'),
        ('apscheduler', 'APScheduler'),
        ('PIL', 'Pillow'),
        ('dotenv', 'python-dotenv')
    ]
    
    missing_packages = []
    
    for package, pip_name in required_packages:
        try:
            __import__(package)
            print(f"✅ {pip_name} is installed")
        except ImportError:
            missing_packages.append(pip_name)
            print(f"❌ {pip_name} is not installed")
    
    if missing_packages:
        print(f"\n⚠️  Missing packages. Install with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    print("=" * 60)
    print("Telegram RAG Chatbot - Setup")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", test_imports),
        ("Environment File", check_env_file),
        ("Environment Variables", check_env_variables),
        ("Directories", create_directories),
        ("Database", initialize_database)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n📋 Checking {check_name}...")
        if not check_func():
            all_passed = False
            print(f"   ⚠️  {check_name} check failed")
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ Setup completed successfully!")
        print("\nYou can now run the bot:")
        print("   cd src")
        print("   python bot.py")
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
        print("\nCommon solutions:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Copy .env.example to .env")
        print("3. Add your API keys to .env")
    
    print("=" * 60)

if __name__ == '__main__':
    main()