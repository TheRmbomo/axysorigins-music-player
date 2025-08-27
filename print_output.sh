#!/bin/bash

if [[ $(jq '.[0].statusCode' test_output.json) -ne 200 ]]; then
	echo jq '.' test_output.json | less -R
	exit $?
fi

html=$(
	jq -r '.[0].body' test_output.json\
		| tidy -iq --show-warnings false --indent --indent-spaces 2 --quiet --tidy-mark no
)

jq --arg new_body "$html"\
	'.[0].body = $new_body' \
	test_output.json \
	| sed -e 's|\\n|\n|g' \
	| sed -e 's|\\"|"|g' \
	| less -R
