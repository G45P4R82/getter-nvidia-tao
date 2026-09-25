.PHONY: init up up-all down restart logs status config smoke test-safe test-auth test-integration

init:
	cp config.env.example config.env
	cp secrets.json.example secrets.json
	chmod 600 secrets.json

up:
	./tao-ftms up

up-all:
	./tao-ftms up-all

down:
	./tao-ftms down

restart:
	./tao-ftms restart

logs:
	./tao-ftms logs

status:
	./tao-ftms status

config:
	./tao-ftms config

smoke:
	./scripts/smoke-test.sh

test-safe:
	pytest -m 'not auth and not integration'

test-auth:
	pytest --run-auth -m 'auth and not integration'

test-integration:
	pytest --run-auth --run-integration -m integration
