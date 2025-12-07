# Development Scripts

This directory contains helper scripts for development workflow.

## Scripts (Created During Phase 0)

The following scripts will be created during Phase 0 implementation:

| Script | Purpose | Created In |
|--------|---------|------------|
| `setup.sh` | One-time setup script (validates Docker, creates .env) | Section 8.1 |
| `validate_setup.py` | Prerequisites validation (checks AWS, API keys) | Section 8.2 |
| `dev.sh` | Development helper (start, stop, logs, test, shell) | Section 8.3 |

## Usage (After Scripts Are Created)

```bash
# One-time setup
./scripts/setup.sh

# Validate prerequisites
python scripts/validate_setup.py

# Development commands
./scripts/dev.sh start      # Start all services
./scripts/dev.sh stop       # Stop all services
./scripts/dev.sh logs       # View logs
./scripts/dev.sh test       # Run tests
./scripts/dev.sh shell      # Open backend shell
./scripts/dev.sh db         # Open database shell
```

## Note

These scripts are created during Phase 0 implementation following the guide in
`PHASE_0_HOW_TO_GUIDE.md` Section 8. This README serves as a placeholder until
the scripts are implemented.

