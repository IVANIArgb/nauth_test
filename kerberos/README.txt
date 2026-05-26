Kerberos + AD для Docker
==========================

1) Скопируйте krb5.conf.example -> krb5.conf и исправьте realm / KDC под ваш домен.

2) Положите keytab для SPN вида HTTP/<KERBEROS_HOSTNAME>@REALM в файл http.keytab
   (команда на контроллере: ktpass или выгрузка из AD — по политике вашей организации).

3) В корне проекта создайте .env из kerberos/env.kerberos.example и заполните
   KERBEROS_HOSTNAME, LDAP_*, REALM.

4) Запуск:
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.kerberos.yml --env-file .env up -d

   Либо: scripts\init_kerberos_docker.ps1 (Windows), затем docker compose ...

Файлы http.keytab и krb5.conf (с секретами) не коммитьте — см. .gitignore.
