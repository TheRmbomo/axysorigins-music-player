#!/bin/bash

TEST_PATH="$1"

if [[ -z "$TEST_PATH" ]]; then
	echo "Usage: $0 <test_json_path>" >&2
	exit 1
fi

test_err=$(jq . "$TEST_PATH" 2>&1 >/dev/null)
if [[ $? -ne 0 ]]; then
	echo "Test contains invalid json:" >&2
	echo "$test_err" >&2
	exit 1
fi

aws lambda invoke --function-name "browse-s3"\
	--payload "file://$TEST_PATH"\
	--cli-binary-format raw-in-base64-out\
	/dev/stdout | jq -s . > test_output.json

./print_output.sh
