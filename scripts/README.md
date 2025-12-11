# Development Scripts

This directory contains helper scripts for development workflow.

## Scripts (Phase 0)

| Script | Purpose | Created In | Status |
|--------|---------|------------|--------|
| `setup.sh` | One-time setup script (validates Docker, creates .env) | Section 8.1 | Available |
| `dev.sh` | Development helper (start, stop, logs, test, shell, clean) | Section 8.3 | Available |
| `validate_setup.py` | Prerequisites validation (checks AWS, API keys) | Section 8.2 | Planned |

`setup.sh` and `dev.sh` are ready to use. `validate_setup.py` will be added in Section 8.2.

## Usage

```bash
# One-time setup
./scripts/setup.sh

# Validate prerequisites
python scripts/validate_setup.py

# Development commands
./scripts/dev.sh start      # Start all services
./scripts/dev.sh stop       # Stop all services
./scripts/dev.sh restart    # Restart services
./scripts/dev.sh logs       # View logs (add args to filter)
./scripts/dev.sh test       # Run backend tests (pass args to pytest)
./scripts/dev.sh shell      # Open backend shell
./scripts/dev.sh clean      # Stop and remove volumes
```
