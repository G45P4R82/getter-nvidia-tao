.PHONY: init up up-all down restart logs status config smoke test-safe test-auth test-integration test-real real-pipeline mcp-install mcp-test mcp-real

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
	python -m unittest discover -s tests -p 'test_api_unittest.py' -v

test-auth:
	TAO_RUN_REAL_TESTS=true python -m unittest tests.test_api_unittest -v

test-integration:
	TAO_RUN_REAL_TESTS=true TAO_RUN_MUTATIONS=true python -m unittest tests.test_api_unittest -v

test-real:
	TAO_RUN_REAL_TESTS=true python scripts/run_unittest_report.py --start-dir tests --experiment "$${TAO_EXPERIMENT_NUMBER:-api-real}"

real-pipeline:
	TAO_RUN_REAL_PIPELINE=true python scripts/run_unittest_report.py --start-dir tests --pattern 'test_real_pipeline_unittest.py' --experiment "$${TAO_EXPERIMENT_NUMBER:-pipeline-real}"

mcp-install:
	python3 -m venv mcp/.venv
	mcp/.venv/bin/pip install -e 'mcp[test]'

mcp-test:
	mcp/.venv/bin/python -m unittest discover -s mcp/tests -v

mcp-real:
	TAO_RUN_REAL_TESTS=true mcp/.venv/bin/python scripts/run_unittest_report.py --start-dir mcp/tests --experiment "$${TAO_EXPERIMENT_NUMBER:-mcp-real}"
