# Runbook: Kerberos SSO до рабочего ответа

## 1) Подготовка AD/Kerberos

1. Создайте/проверьте сервисную учетную запись в AD.
2. Зарегистрируйте SPN `HTTP/<fqdn>`:
   - `setspn -S HTTP/app.example.com svc_kerberos`
3. Сгенерируйте keytab:
   - `ktpass /princ HTTP/app.example.com@EXAMPLE.COM /mapuser svc_kerberos@EXAMPLE.COM /pass <password> /crypto AES256-SHA1 /ptype KRB5_NT_PRINCIPAL /out service.keytab`
4. Запустите `kerberos_ad_service/scripts/setup_ad.ps1` для автоматической проверки.

## 2) Локальный Docker запуск

1. Перейдите в `kerberos_ad_service`.
2. Скопируйте `.env.example` в `.env` и подставьте реальные значения.
3. Положите keytab в `kerberos_ad_service/secrets/service.keytab`.
4. Запустите:
   - `docker compose build`
   - `docker compose up -d`
5. Проверьте preflight:
   - `docker compose logs -f kerberos-sso`

## 3) Проверка Kerberos/LDAP в контейнере

1. `docker exec -it kerberos-sso sh`
2. `kinit -k -t /run/secrets/service_keytab HTTP/<fqdn>@<REALM>`
3. `klist`
4. `nslookup dc01.example.com`
5. `nc -vz dc01.example.com 88`
6. `nc -vz dc01.example.com 389`
7. `ldapsearch -H ldap://dc01.example.com -Y GSSAPI -b "DC=example,DC=com" "(sAMAccountName=test)"`

## 4) Проверка API

1. Health:
   - `curl http://localhost:5000/health`
2. Метрики:
   - `curl http://localhost:5000/metrics`
3. Kerberos auth:
   - `curl -v --negotiate -u : http://localhost:5000/auth/me`

Ожидаемый результат: JSON со статусом `ok`, `username`, `principal`, `ad_user`.

## 5) Частые ошибки и причины

- `Keytab not found`:
  - неверный путь, не примонтирован secret.
- `kinit: Client not found in Kerberos database`:
  - некорректный principal/SPN.
- `Server not found in Kerberos database`:
  - SPN не зарегистрирован или не тот FQDN.
- `Cannot contact any KDC`:
  - DNS/маршрут/файрвол до порта 88.
- `LDAP bind failed`:
  - GSSAPI контекст не поднят, KRB ticket отсутствует/просрочен.
- `User not found in AD`:
  - неверный `LDAP_BASE_DN` или `sAMAccountName`.

## 6) Kubernetes rollout

1. В `.env` заполните:
   - `K8S_NAMESPACE`, `K8S_HOSTNAME`, `IMAGE`
2. Сгенерируйте манифесты из `.env`:
   - `make k8s-render`
3. Примените namespace/config/redis/service/ingress/deployment:
   - `make k8s-deploy`
2. Создайте k8s secret из keytab+krb5:
   - `make k8s-secret`
3. Дождитесь статуса:
   - `kubectl -n kerberos-sso rollout status deployment/kerberos-sso`
4. Проверьте pod‑логи:
   - `kubectl -n kerberos-sso logs -l app=kerberos-sso --tail=200`

## 7) CI/CD секреты

Для автодеплоя через GitHub Actions:

- `KUBE_CONFIG_BASE64`
- `KUBE_NAMESPACE`

После этого push в `main` запускает test/build/publish/deploy pipeline.
