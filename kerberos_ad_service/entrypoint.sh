#!/usr/bin/env sh
set -eu

log() {
  printf '%s %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1"
}

KRB5_CONFIG_PATH="${KRB5_CONFIG:-/etc/krb5.conf}"
KEYTAB_PATH="${KERBEROS_KEYTAB:-/run/secrets/service_keytab}"
SPN_HOST="${SPN_HOSTNAME:-localhost}"
REALM="${KERBEROS_REALM:-EXAMPLE.COM}"
SERVICE_NAME="${KERBEROS_SERVICE_NAME:-HTTP}"
LDAP_HOST="${LDAP_URI:-}"

if [ "${PREFLIGHT_ENABLED:-true}" = "true" ]; then
  log "Running preflight diagnostics"

  if [ ! -f "${KRB5_CONFIG_PATH}" ]; then
    log "ERROR: krb5 config not found: ${KRB5_CONFIG_PATH}"
    exit 1
  fi

  if [ ! -f "${KEYTAB_PATH}" ]; then
    log "ERROR: keytab not found: ${KEYTAB_PATH}"
    exit 1
  fi

  chmod 0400 "${KEYTAB_PATH}" 2>/dev/null || true

  if [ "${PREFLIGHT_KINIT_ENABLED:-true}" = "true" ]; then
    PRINCIPAL="${SERVICE_NAME}/${SPN_HOST}@${REALM}"
    log "Validating keytab using kinit for ${PRINCIPAL}"
    kinit -k -t "${KEYTAB_PATH}" "${PRINCIPAL}"
    klist
  fi

  if [ -n "${LDAP_HOST}" ]; then
    LDAP_HOST_CLEAN="$(printf "%s" "${LDAP_HOST}" | sed -E 's#^ldaps?://##' | sed -E 's#/.*$##' | sed -E 's#:[0-9]+$##')"
    if [ -n "${LDAP_HOST_CLEAN}" ]; then
      log "Checking DNS for ${LDAP_HOST_CLEAN}"
      nslookup "${LDAP_HOST_CLEAN}" >/dev/null
    fi
  fi
fi

log "Starting Flask service"
exec python app.py
