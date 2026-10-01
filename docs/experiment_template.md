# Experiment <number>

Use `scripts/run_unittest_report.py` to generate one report for every test
round. Reports must be named `docs/experiment_<number>.md`.

Required sections:

- Status.
- Date and host.
- Test scope and command.
- TAO API version.
- Dataset/workspace identifiers without credentials.
- Tests executed, passed, failed, errors and skipped.
- Job IDs and final statuses for real TAO runs.
- Generated artifacts.
- System behavior during the run.
- Failures and corrective actions.
- Final conclusion.

Never include NGC keys, JWTs, passwords, authorization headers, or raw secret
configuration in a report.
