#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info() { printf '[INFO] %s\n' "$*"; }
error() { printf '[ERROR] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Usage: ./scripts/dev.sh <command> [args...]

Commands:
  start            Start all services (docker compose up -d)
  stop             Stop services (docker compose down)
  restart          Restart services (down then up)
  logs [args...]   Follow logs (docker compose logs -f)
  test [args...]   Run backend tests (docker compose exec backend pytest)
  shell            Open backend shell (docker compose exec backend bash)
  clean            Stop services and remove volumes (docker compose down -v)
USAGE
}

COMPOSE_CMD=()

determine_compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
    return
  fi

  error "Docker Compose is required. Install Docker Desktop/Engine (Compose v2)."
  exit 1
}

ensure_docker_running() {
  if ! command -v docker >/dev/null 2>&1; then
    error "Docker is not installed. Install Docker Desktop/Engine and retry."
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    error "Docker is installed but not running. Start Docker and rerun."
    exit 1
  fi
}

start_services() {
  "${COMPOSE_CMD[@]}" up -d
}

stop_services() {
  "${COMPOSE_CMD[@]}" down
}

restart_services() {
  stop_services
  start_services
}

logs_services() {
  "${COMPOSE_CMD[@]}" logs -f "$@"
}

test_backend() {
  "${COMPOSE_CMD[@]}" exec backend pytest "$@"
}

shell_backend() {
  "${COMPOSE_CMD[@]}" exec backend bash
}

clean_services() {
  "${COMPOSE_CMD[@]}" down -v
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 1
  fi

  determine_compose_cmd
  ensure_docker_running
  cd "$PROJECT_ROOT"

  case "$1" in
    start)
      start_services
      ;;
    stop)
      stop_services
      ;;
    restart)
      restart_services
      ;;
    logs)
      shift
      logs_services "$@"
      ;;
    test)
      shift
      test_backend "$@"
      ;;
    shell)
      shell_backend
      ;;
    clean)
      clean_services
      ;;
    *)
      error "Unknown command: $1"
      usage
      exit 1
      ;;
  esac
}

trap 'error "Command failed (line ${LINENO})."' ERR

main "$@"
