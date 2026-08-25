# Azure Incident Response Agent and Local Monitoring Dashboard

This project is being implemented from the approved specification in `SPEC.md` and ordered plan in `TASKS.md`.

## Development setup

Python 3.11 or later is required. Create an isolated environment and install the pinned dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The deterministic offline default test command is:

```bash
.venv/bin/python -m pytest -q
```

No live RSS feed or LLM is used by the default tests.
