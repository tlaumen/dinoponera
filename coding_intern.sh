#!/usr/bin/env bash

AGENT_FILE=".pi/agent/INTERN.md"
EXECUTION_DISCIPLINE_FILE=".pi/agent/EXECUTION_DISCIPLINE.md"

while true; do
    pi --system-prompt "$AGENT_FILE" --append-system-prompt "$EXECUTION_DISCIPLINE_FILE"

    read -rp "Continue? [Y/n] " answer
    case "${answer,,}" in
        n) break ;;
    esac
done
