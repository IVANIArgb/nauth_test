.PHONY: build run debug test k8s-render k8s-secret k8s-deploy

build:
	docker compose build

run:
	docker compose up -d

debug:
	APP_ENV=dev DEBUG=true docker compose up --build

test:
	chmod +x test.sh tests/smoke/smoke_test.sh && ./test.sh

k8s-secret:
	chmod +x scripts/create_k8s_secret.sh && ./scripts/create_k8s_secret.sh

k8s-render:
	python3 scripts/render_k8s_from_env.py

k8s-deploy:
	chmod +x scripts/deploy_k8s.sh && ./scripts/deploy_k8s.sh
