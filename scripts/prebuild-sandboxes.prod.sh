#!/usr/bin/env bash
# PRODUCTION deploy step -- run once after `up -d`, and again whenever a sandbox
# Dockerfile or its image tag changes.
#
#   ./scripts/prebuild-sandboxes.prod.sh              # build every environment
#   ./scripts/prebuild-sandboxes.prod.sh python-ml    # skip python-ml (multi-GB CUDA base)
#
# Why this exists: DockerSandboxRunner._ensure_image builds an image lazily, on the first
# request that needs it. Without this step the first learner to open a coding lesson waits
# through a full image build inside a 20s request and times out. Building ahead of time
# moves that cost to deploy.
#
# The image list is read from _ENVIRONMENTS in sandbox_runner/runner.py rather than
# duplicated here, so adding an environment or bumping an image tag needs no edit to this
# script. It runs inside the sandbox-runner container, which is the one place that already
# has both the registry and docker.sock.
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose -f docker-compose.prod.yml --env-file .env.prod \
	exec -T sandbox-runner python - "$@" <<'PY'
import sys

import docker
import docker.errors

from sandbox_runner.runner import _ENVIRONMENTS

skip = set(sys.argv[1:])
client = docker.from_env()
failed = []

for environment_id, environment in _ENVIRONMENTS.items():
    if environment_id in skip:
        print(f"skip   {environment_id}", flush=True)
        continue
    try:
        client.images.get(environment.image)
        print(f"have   {environment_id}  ({environment.image})", flush=True)
        continue
    except docker.errors.ImageNotFound:
        pass
    print(f"build  {environment_id}  ({environment.image}) ...", flush=True)
    try:
        client.images.build(path=str(environment.dockerfile_dir), tag=environment.image, rm=True)
        print(f"built  {environment_id}", flush=True)
    except docker.errors.APIError as exc:
        # Keep going: one unbuildable environment should not block the rest, and the
        # summary below is what tells you which lessons will fail at request time.
        print(f"FAIL   {environment_id}: {exc}", flush=True)
        failed.append(environment_id)

if failed:
    print(f"\n{len(failed)} environment(s) failed to build: {', '.join(failed)}")
    sys.exit(1)
print("\nAll sandbox images ready.")
PY
