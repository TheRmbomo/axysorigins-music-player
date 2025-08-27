import os
from typing import Dict, Any

PASSWORD = os.getenv('PLAYER_PASSWORD', '')

def route(event: Any, path: str) -> Dict[str, Any] | None:
    if PASSWORD == '':
        return {"statusCode": 500, "body": "PLAYER_PASSWORD is missing."}

    response_headers = {}

    if path == 'password':
        pw = event['queryStringParameters'].get('password')
        if pw != PASSWORD:
            return {"statusCode": 401, "body": "Incorrect password."}

        response_headers['Set-Cookie'] = 'Signed-In=true; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=2592000;'
        response_headers['HX-Refresh'] = 'true'
        return {"statusCode": 204, "headers": response_headers, "body": ""}
