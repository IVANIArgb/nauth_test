#!/usr/bin/env bash
set -euo pipefail

python3 scripts/render_k8s_from_env.py

NAMESPACE="${NAMESPACE:-${K8S_NAMESPACE:-kerberos-sso}}"

kubectl apply -f k8s/generated/namespace.yaml
kubectl apply -f k8s/generated/configmap.yaml
kubectl apply -f k8s/generated/redis.yaml
kubectl apply -f k8s/generated/service.yaml
kubectl apply -f k8s/generated/ingress.yaml

kubectl apply -f k8s/generated/deployment.yaml

kubectl -n "${NAMESPACE}" rollout status deployment/kerberos-sso --timeout=180s
echo "Kubernetes deployment completed."
