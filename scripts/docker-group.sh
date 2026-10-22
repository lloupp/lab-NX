#!/usr/bin/env bash

docker_with_group() {
    if docker info >/dev/null 2>&1; then
        docker "$@"
        return
    fi

    local command
    printf -v command '%q ' docker "$@"
    sg docker -c "$command"
}
