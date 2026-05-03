#!/usr/bin/env bash
# Wrapper that calls the Python daemon starter
exec python3 "$(dirname "$0")/start-daemons.py"
