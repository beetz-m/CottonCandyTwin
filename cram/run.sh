#!/usr/bin/env bash
# Run a command in the CRAM environment (cram-env + ROS Jazzy + ~/ros_ws for the robot descriptions),
# with the cotton_candy package on the path.  Usage: cram/run.sh python cram/demo.py | cram/run.sh pytest cram/tests
set -eo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source /opt/ros/jazzy/setup.bash
source ~/ros_ws/install/setup.bash
# the stand-alone cramera's question engine (cramera_bridge.questions) for the competency questions: cramera left the
# CRAM monorepo in November 2026; its question engine imports only krrood, so it runs in cram-env (read-only use)
CRAMERA_PACKAGES="$HOME/cramera/packages"
export PYTHONPATH="$HERE:$CRAMERA_PACKAGES/bridge/src:$CRAMERA_PACKAGES/protocol/src:$CRAMERA_PACKAGES/viewer/src:${PYTHONPATH:-}"
CMD="$1"; shift
case "$CMD" in
  python) exec ~/.virtualenvs/cram-env/bin/python "$@" ;;
  pytest) exec ~/.virtualenvs/cram-env/bin/python -m pytest -p no:launch_testing -p no:launch_ros -p no:launch_pytest -q "$@" ;;
  *) exec ~/.virtualenvs/cram-env/bin/"$CMD" "$@" ;;
esac
