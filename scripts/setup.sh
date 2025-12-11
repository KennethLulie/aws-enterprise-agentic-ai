#!/usr/bin/env bash
# Configurable env vars:
# - AWS_PROFILE (default: default)
# - AWS_REGION / AWS_DEFAULT_REGION (default: us-east-1)
# - PULL_TIMEOUT_SECONDS (default: 120; docker pull timeout)
# - DOCKER_CHECK_TIMEOUT (default: 10; docker status check timeout)
# - CI=true (skip docker pulls)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PULL_TIMEOUT_SECONDS="${PULL_TIMEOUT_SECONDS:-120}"
DOCKER_CHECK_TIMEOUT="${DOCKER_CHECK_TIMEOUT:-10}"

info() { printf '[INFO] %s\n' "$*"; }
error() { printf '[ERROR] %s\n' "$*" >&2; }

check_command() {
  command -v "$1" >/dev/null 2>&1
}

run_with_timeout() {
  local seconds="$1"
  shift
  if check_command timeout; then
    timeout "$seconds" "$@"
  else
    "$@"
  fi
}

ensure_docker() {
  if ! check_command docker; then
    error "Docker is not installed. Install Docker Desktop/Engine and rerun."
    exit 1
  fi

  if ! run_with_timeout "$DOCKER_CHECK_TIMEOUT" docker version >/dev/null 2>&1; then
    error "Docker is installed but unreachable. Ensure the daemon is running and try again."
    exit 1
  fi

  if ! run_with_timeout "$DOCKER_CHECK_TIMEOUT" docker info >/dev/null 2>&1; then
    error "Docker daemon is not running or not reachable. Start Docker and rerun."
    exit 1
  fi

  info "Docker is installed and running."
}

ensure_python() {
  local python_bin=""

  if check_command python3; then
    python_bin="python3"
  elif check_command python; then
    python_bin="python"
  else
    error "Python 3.11+ is required. Install Python and rerun."
    exit 1
  fi

  local version
  version="$("$python_bin" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"

  local major minor
  major=$(printf '%s' "$version" | cut -d. -f1)
  minor=$(printf '%s' "$version" | cut -d. -f2)

  if (( major < 3 || (major == 3 && minor < 11) )); then
    error "Python ${version} detected. Python 3.11+ is required."
    exit 1
  fi

  info "Python ${version} detected."
}

ensure_aws_cli() {
  if ! check_command aws; then
    error "AWS CLI v2 is required. Install it and run 'aws configure' before retrying."
    exit 1
  fi

  local region default_region profile
  region="${AWS_REGION:-us-east-1}"
  default_region="${AWS_DEFAULT_REGION:-$region}"
  profile="${AWS_PROFILE:-default}"

  info "Using AWS profile '${profile}' with region '${region}'."

  if ! AWS_PROFILE="$profile" AWS_REGION="$region" AWS_DEFAULT_REGION="$default_region" aws sts get-caller-identity --query Account --output text >/dev/null 2>&1; then
    error "AWS CLI is installed but credentials are missing or invalid for profile '${profile}'. Run 'aws configure' or set AWS_PROFILE to a valid profile."
    exit 1
  fi

  info "AWS CLI is installed and credentials are configured (region: ${region})."
}

ensure_env_file() {
  if [ ! -f "${PROJECT_ROOT}/.env.example" ]; then
    error ".env.example is missing in ${PROJECT_ROOT}. Cannot create .env."
    exit 1
  fi

  if [ -f "${PROJECT_ROOT}/.env" ]; then
    info ".env already exists. Skipping creation."
  else
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    info "Created .env from .env.example."
  fi
}

prepull_images() {
  if [[ "${CI:-}" == "true" ]]; then
    info "CI environment detected; skipping Docker image pulls."
    return
  fi

  info "Pre-pulling Docker base images..."

  pull_image_with_cache() {
    local image="$1"
    if docker image inspect "$image" >/dev/null 2>&1; then
      info "$image already present; skipping pull."
      return 0
    fi

    local pull_cmd=(docker pull "$image")
    if check_command timeout; then
      pull_cmd=(timeout "${PULL_TIMEOUT_SECONDS}" "${pull_cmd[@]}")
    fi

    if ! "${pull_cmd[@]}"; then
      error "Failed to pull $image. Check network connectivity, Docker Hub access, or increase PULL_TIMEOUT_SECONDS."
      exit 1
    fi
  }

  pull_image_with_cache "python:3.11-slim"
  pull_image_with_cache "node:20-alpine"

  info "Docker images are available locally."
}

main() {
  cd "$PROJECT_ROOT"

  info "Local development setup; run inside WSL2 or Linux with Docker available."
  info "Starting setup checks..."
  ensure_docker
  ensure_python
  ensure_aws_cli
  ensure_env_file
  prepull_images

  info "Setup completed successfully."
}

main "$@"
