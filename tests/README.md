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

Run safe system and frontier tests. These do not authenticate or create TAO
resources:

```bash
pytest -m 'not auth and not integration'
```

Run authenticated regression tests with a key kept in the shell environment:

```bash
export NGC_KEY='do-not-paste-this-in-a-repository'
pytest --run-auth -m 'auth and not integration'
```

Alternatively, use an existing JWT:

```bash
export TAO_TOKEN='jwt-value'
pytest --run-auth -m 'auth and not integration'
```

Run the workspace integration lifecycle. This creates and deletes a temporary
workspace and should only be used in a test project:

```bash
pytest --run-auth --run-integration -m integration
```

The suite never starts training by default. Training integration needs a
versioned dataset, a test workspace, a GPU budget, and an explicit separate
test before it should be enabled in CI.

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

- `test_system.py`: health, OpenAPI, ReDoc, and routing.
- `test_authentication.py`: NGC login, JWT protection, and invalid credentials.
- `test_regression.py`: authenticated read-only API contracts.
- `test_frontier.py`: malformed, oversized, unknown, and invalid inputs.
- `test_integration.py`: opt-in workspace create/read/delete lifecycle.

The tests intentionally do not print response bodies for authentication
failures so API keys and JWTs are not leaked into CI logs.
