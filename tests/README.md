# TAO FTMS Tests

Install dependencies:

```bash
python3 -m pip install -r tests/requirements.txt
```

Set the API URL:

```bash
export TAO_BASE_URL=http://100.107.81.126:8090
export TAO_ORG=getter
```

Run real API system and frontier tests:

```bash
TAO_RUN_REAL_TESTS=true python -m unittest discover -s tests -v
```

Run authenticated regression tests with a key kept in the shell environment:

```bash
export NGC_KEY='do-not-paste-this-in-a-repository'
TAO_RUN_REAL_TESTS=true python -m unittest discover -s tests -v
```

Alternatively, use an existing JWT:

```bash
export TAO_TOKEN='jwt-value'
TAO_RUN_REAL_TESTS=true python -m unittest discover -s tests -v
```

Run the workspace integration lifecycle. This creates and deletes a temporary
workspace and should only be used in a test project:

```bash
TAO_RUN_REAL_TESTS=true TAO_RUN_MUTATIONS=true \
  python -m unittest discover -s tests -v
```

The suite never starts training by default. Training integration needs a
versioned dataset, a test workspace, a GPU budget, and an explicit separate
test before it should be enabled in CI.

## Real Training Pipeline

The training test submits a real GPU job. Configure a dedicated test workspace,
dataset URI, and JSON specs before running it:

```bash
export TAO_TEST_WORKSPACE_ID='workspace-uuid'
export TAO_TRAIN_DATASET_URI='seaweedfs://tao-storage/data/tao-test-classification-v1'
export TAO_TRAIN_SPECS_JSON='{"train":{"num_epochs":1},"dataset":{"num_classes":2}}'
TAO_RUN_REAL_PIPELINE=true python -m unittest tests.test_real_pipeline_unittest -v
```

Evaluation, ONNX export, TensorRT engine generation, and TensorRT inference are
enabled separately because they consume more time and artifacts:

```bash
export TAO_RUN_REAL_DEPLOY=true
export TAO_EVAL_SPECS_JSON='...'
export TAO_EXPORT_SPECS_JSON='...'
export TAO_TRT_SPECS_JSON='...'
export TAO_INFERENCE_SPECS_JSON='...'
python -m unittest tests.test_real_pipeline_unittest -v
```

These tests use the real FTMS API, storage, Docker jobs, GPU, checkpoints, and
TensorRT. They do not use mocked HTTP responses.

## GitHub Actions

The workflow is `.github/workflows/tao-api-tests.yml`. Because the current TAO
endpoint is on a private `100.107.81.126` address, the repository needs a
self-hosted runner with these labels:

```text
self-hosted, linux, tao-ftms
```

Configure these repository variables:

```text
TAO_BASE_URL=http://100.107.81.126:8090
TAO_ORG=getter
```

Configure these repository secrets. At least one is required for the
authenticated job:

```text
NGC_API_KEY
TAO_TOKEN
```

The integration job is manual-only and creates then deletes a temporary
workspace. It is enabled from **Actions -> TAO API Tests -> Run workflow**.

## Test Layers

- `test_api_unittest.py`: real health, OpenAPI, authentication, regression,
  frontier, and optional workspace lifecycle tests.
- `test_real_pipeline_unittest.py`: real training and optional deployment pipeline.

The tests intentionally do not print response bodies for authentication
failures so API keys and JWTs are not leaked into CI logs.
