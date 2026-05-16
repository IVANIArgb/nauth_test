#!/bin/bash
# Скрипт для настройки Kerberos окружения

echo "🔐 Настройка Kerberos окружения..."

# Создание директорий
mkdir -p kerberos/{keytabs,logs,conf}

# Копирование конфигурации
cp krb5.conf kerberos/conf/

# Установка переменных окружения
export KRB5_CONFIG=kerberos/conf/krb5.conf
export KRB5_KDC_PROFILE=kerberos/conf/kdc.conf

echo "✅ Kerberos окружение настроено"
echo "📁 Конфигурация: kerberos/conf/"
echo "🔑 Keytabs: kerberos/keytabs/"
echo "📝 Логи: kerberos/logs/"

# Создание тестового keytab файла (пустой)
touch kerberos/keytabs/http.keytab
echo "🔑 Создан тестовый keytab файл"

echo ""
echo "🚀 Для запуска приложения используйте:"
echo "export KRB5_CONFIG=kerberos/conf/krb5.conf"
echo "python run.py"
