#!/bin/bash

LOG_GROUP_NAME="$1"
if [[ -z "$LOG_GROUP_NAME" ]]; then
	echo "Usage: $0 <log_group_name>" >&2
	exit 1
fi

aws logs tail "$LOG_GROUP_NAME" --follow --since 10m --format json
