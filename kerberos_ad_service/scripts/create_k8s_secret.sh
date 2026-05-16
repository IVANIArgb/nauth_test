#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-kerberos-sso}"
SECRET_NAME="${SECRET_NAME:-kerberos-sso-secrets}"
KEYTAB_PATH="${KEYTAB_PATH:-./secrets/service.keytab}"
KRB5_PATH="${KRB5_PATH:-./krb5.conf}"

if [[ ! -f "${KEYTAB_PATH}" ]]; then
  echo "Keytab not found: ${KEYTAB_PATH}"
  exit 1
fi

if [[ ! -f "${KRB5_PATH}" ]]; then
  echo "krb5.conf not found: ${KRB5_PATH}"
  exit 1
fi

kubectl -n "${NAMESPACE}" create secret generic "${SECRET_NAME}" \
  --from-file=service.keytab="${KEYTAB_PATH}" \
  --from-file=krb5.conf="${KRB5_PATH}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret ${SECRET_NAME} applied in namespace ${NAMESPACE}."
