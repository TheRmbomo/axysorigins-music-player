#!/bin/bash

FUNCTION_NAME="${1:-$MUSIC_LAMBDA}"
if [[ -z "$FUNCTION_NAME" ]]; then
	echo "Usage: $0 <function_name>" >&2
	exit 1
fi

if ! [[ -f "lambda_files.txt" ]]; then
	echo "Missing \"lambda_files.txt\"" >&2
	exit 1
fi

hash=$(
	while IFS= read -r f; do
		if [[ -z "$f" ]]; then continue; fi
		# echo "$f" >/dev/tty

		if ! [[ -f "$f" ]]; then
			echo "Missing \"$f\"" >&2
			exit 1
		fi

		cat -- "$f"
	done < lambda_files.txt | sha256sum | head -c 64
)

old_hash=$(cat hash.txt)
if [ "$hash" = "$old_hash" ]; then
	echo "No changes detected. Aborting." >&2
	exit 2
fi

echo "$hash" > hash.txt

zip -q lambda.zip -@ < lambda_files.txt

aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file "fileb://./lambda.zip"\
	| less
