#!/usr/bin/env python3
"""
Простой скрипт для инициализации БД с Kerberos таблицами
Без импорта аутентификации для избежания ошибок
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

# Создание базового класса
Base = declarative_base()

class KerberosUser(Base):
    """Модель для Kerberos пользователей"""
    __tablename__ = 'kerberos_users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    principal = Column(String(200), nullable=False, unique=True, index=True)  # username@REALM
    realm = Column(String(100), nullable=False, index=True)
    full_name = Column(String(200), nullable=True)
    department = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default='user')
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<KerberosUser(username='{self.username}', principal='{self.principal}', role='{self.role}')>"


class KerberosSession(Base):
    """Модель для Kerberos сессий"""
    __tablename__ = 'kerberos_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False, index=True)
    principal = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<KerberosSession(session_id='{self.session_id}', username='{self.username}')>"


def init_kerberos_database():
    """Инициализация БД с Kerberos таблицами"""
    print("🔐 Инициализация Kerberos БД...")
    
    try:
        # Путь к БД (единый с приложением: project_root/database/users_courses.db)
        project_root = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(project_root, 'database', 'users_courses.db')
        database_url = f"sqlite:///{db_path}"
        
        # Создание движка и сессии
        engine = create_engine(database_url, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Создание всех таблиц
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы")
        
        # Создание тестовых Kerberos пользователей
        session = SessionLocal()
        try:
            # Проверяем, есть ли уже Kerberos пользователи
            if session.query(KerberosUser).count() > 0:
                print("ℹ️  Kerberos пользователи уже существуют")
                return
            
            print("📝 Создание тестовых Kerberos пользователей...")
            
            kerberos_users_data = [
                {
                    'username': 'admin',
                    'principal': 'admin@EXAMPLE.COM',
                    'realm': 'EXAMPLE.COM',
                    'full_name': 'Администратор Kerberos',
                    'department': 'IT отдел',
                    'email': 'admin@example.com',
                    'role': 'admin',
                    'is_active': True,
                },
                {
                    'username': 'kerberos_user',
                    'principal': 'kerberos_user@EXAMPLE.COM',
                    'realm': 'EXAMPLE.COM',
                    'full_name': 'Kerberos Пользователь',
                    'department': 'Тестирование',
                    'email': 'kerberos@example.com',
                    'role': 'admin',
                    'is_active': True,
                },
                {
                    'username': 'testuser',
                    'principal': 'testuser@EXAMPLE.COM',
                    'realm': 'EXAMPLE.COM',
                    'full_name': 'Тестовый Пользователь',
                    'department': 'Разработка',
                    'email': 'test@example.com',
                    'role': 'user',
                    'is_active': True,
                },
                {
                    'username': 'пользователь',
                    'principal': 'пользователь@EXAMPLE.COM',
                    'realm': 'EXAMPLE.COM',
                    'full_name': 'Пользователь Системы',
                    'department': 'IT отдел',
                    'email': 'user@example.com',
                    'role': 'admin',
                    'is_active': True,
                }
            ]
            
            for user_data in kerberos_users_data:
                kerberos_user = KerberosUser(**user_data)
                session.add(kerberos_user)
            
            session.commit()
            print("✅ Kerberos пользователи созданы")
            
            # Показать созданных пользователей
            users = session.query(KerberosUser).all()
            print(f"\n📋 Создано пользователей: {len(users)}")
            for user in users:
                print(f"   👤 {user.username} ({user.principal}) - {user.role}")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Ошибка при создании Kerberos пользователей: {e}")
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

if __name__ == "__main__":
    init_kerberos_database()
