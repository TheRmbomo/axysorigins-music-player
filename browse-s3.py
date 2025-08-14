import os.path
from enum import Enum
import base64
import urllib.parse
import gzip
import re
from http import cookies

import boto3
from botocore.exceptions import ClientError

PASSWORD = os.getenv('PLAYER_PASSWORD', '')
BUCKET = os.getenv('PLAYER_BUCKET', '') # e.g. player-files
URL = os.getenv('PLAYER_URL', '').rstrip('/') # e.g. https://example-website.com/player
INDEX = os.getenv('PLAYER_INDEX', '').lstrip('/').rstrip('/') # e.g. index
IMAGES = os.getenv('PLAYER_IMAGES', '').rstrip('/') # e.g. https://example-website.com/images

season_map = {"1": "Winter", "2": "Spring", "3": "Summer", "4": "Fall"}

s3_client = boto3.client('s3')

class ItemType(Enum):
    UNKNOWN = 0
    FOLDER = 1
    FILE = 2

def handler(event, _):
    print(event)

    if PASSWORD == '':
        return {"statusCode": 500, "body": "PLAYER_PASSWORD is missing."}

    response_headers = {}

    path = urllib.parse.unquote(event['pathParameters']['proxy'])
    if path.lstrip('/').rstrip('/') == 'password':
        pw = event['queryStringParameters'].get('password')
        if pw != PASSWORD:
            return {"statusCode": 401, "body": "Incorrect password."}
        response_headers['Set-Cookie'] = 'Signed-In=true; Path=/; Secure; HttpOnly; SameSite=Strict;'
        response_headers['HX-Refresh'] = 'true'
        path = INDEX
        return {"statusCode": 204, "headers": response_headers, "body": ""}

    if BUCKET == '':
        return {"statusCode": 500, "body": "PLAYER_BUCKET is missing."}
    if URL == '':
        return {"statusCode": 500, "body": "PLAYER_URL is missing."}
    if INDEX == '':
        return {"statusCode": 500, "body": "PLAYER_INDEX is missing."}
    if IMAGES == '':
        return {"statusCode": 500, "body": "PLAYER_IMAGES is missing."}

    request_headers = event.get('headers') or {}

    cookie = request_headers.get('cookie') or request_headers.get('Cookie') or ''
    C = cookies.SimpleCookie()
    C.load(cookie)

    HX_REQUEST = (
        request_headers.get('Hx-Request')
        or request_headers.get('HX-Request')
        or request_headers.get('hx-request')
    ) == 'true' and (
        request_headers.get('Hx-History-Restore-Request')
        or request_headers.get('HX-History-Restore-Request')
        or request_headers.get('hx-history-restore-request')
    ) != 'true'

    item_type = ItemType.UNKNOWN
    response = None

    if path.endswith('/'):
        try:
            response = get_s3_folder(BUCKET, path)
            item_type = ItemType.FOLDER
        except ClientError:
            try:
                response = get_s3_file(BUCKET, path)
                item_type = ItemType.FILE
            except ClientError:
                return {"statusCode": 404, "body": "Path does not exist as a file or a folder path."}
    else:
        try:
            response = get_s3_file(BUCKET, path)
            item_type = ItemType.FILE
        except ClientError:
            try:
                response = get_s3_folder(BUCKET, path)
                item_type = ItemType.FOLDER
            except ClientError:
                return {"statusCode": 404, "body": "Failed to find file."}

    parent_folder_content = ""
    error = ""

    name = "Seasons Music"
    description = "A personal music player."
    logo = f"{IMAGES}/logo-small-a.png"
    url = f'{URL}/{path}'

    match item_type:
        case ItemType.FOLDER:
            folder = os.path.basename(path)

            match = re.match(r"(\d{1,2})-(1|2|3|4)", folder)
            if match:
                year = "20" + match.group(1)
                season = season_map.get(match.group(2), "")
                name = f"{year} {season} | Seasons Music"
                description = f"Some anime music from the {year} {season} season"
            elif folder != INDEX:
                name = f"{folder} | Seasons Music"

            folder = display_folder_contents(path, response)

            hx_fragment = f"""\
            <title id="title" hx-swap-oob="true">{name}</title>
            {folder}"""

            audio = (
                get_file_template("")
                + '<script id="load-music" type="text/javascript"></script>'
            )
        case ItemType.FILE:
            url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    "Bucket": BUCKET,
                    "Key": path,
                },
                ExpiresIn=60*30 # 30 minutes in seconds
            )

            parent = os.path.dirname(path.rstrip('/')) + '/'

            try:
                parent_folder_content = display_folder_contents(parent, get_s3_folder(BUCKET, parent))
            except:
                error = "Failed to list parent folder."

            full_name = os.path.splitext(path)[0]
            name = f"{os.path.basename(full_name)} | Seasons Music"

            with open('loadMusic.js') as load_music_file:
                load_music = load_music_file.read()

            hx_fragment = f"""\
            <title id="title" hx-swap-oob="true">{name}</title>
            <script id="load-music" hx-swap-oob="true" type="text/javascript">
                {load_music\
                    .replace("{{ url }}", url.replace("'", "\\'"))
                    .replace("{{ name }}", full_name.replace("'", "\\'"))
                    .replace("{{ loadPlayer }}", 'loadPlayer()' if HX_REQUEST else '')
                }
            </script>"""

            audio = get_file_template(
                f"""\
                <button
                    id="load-button" onclick="loadPlayer()"
                    class="bg-red-600 p-2 rounded-md"
                >Click to start loading</button>"""
            )

    status = 200

    signed_in = C.get('Signed-In')
    if signed_in:
        signed_in = signed_in.value
    signed_in = bool(signed_in)

    if HX_REQUEST:
        if not signed_in:
            status = 403
            body = ""
        else:
            body = hx_fragment
    else:
        with open('index.html') as index_file:
            index = index_file.read()

        css = ""
        if signed_in:
            with open("index.css") as css_file:
                css = css_file.read()

        body = index\
            .replace('{{ name }}', name)\
            .replace('{{ logo }}', logo)\
            .replace('{{ description }}', description)\
            .replace('{{ url }}', url)\
            .replace('{{ css }}', css)

        if signed_in:
            body = body.replace('{{ content }}', (
                audio
                + hx_fragment
                + parent_folder_content
                + get_error_content(error)
            ))
        else:
            with open('password.html') as password_file:
                password = password_file.read()
            body = body.replace('{{ content }}', password.replace('{{ url }}', URL))

    # Remove leading spaces on each line
    body = '\n'.join([line.lstrip() for line in body.splitlines()])

    response_headers['Content-Type'] = 'text/html'
    response_headers['Vary'] = 'Hx-Request'
    response_headers['Content-Encoding'] = 'gzip'

    return {
        "statusCode": status,
        "headers": response_headers,
        "isBase64Encoded": True,
        "body": base64.b64encode(gzip.compress(body.encode('utf-8'))).decode('utf-8'),
    }

def get_s3_folder(bucket_name, path):
    path = path.lstrip('/').rstrip('/') + '/'
    return s3_client.list_objects_v2(Bucket=bucket_name, Prefix=path, Delimiter='/')

def get_s3_file(bucket_name, path):
    return s3_client.get_object(Bucket=bucket_name, Key=path)

def display_folder_contents(path, response):
    path = path.lstrip('/').rstrip('/') + '/'

    reverse = (path == INDEX + '/')

    files = sorted(
        [key['Key'] for key in response.get('Contents', [])]
        + [folder['Prefix'] for folder in response.get('CommonPrefixes', [])],
        key=music_order, reverse=reverse
    )

    try:
        files.remove(path)
    except:
        pass

    parent = os.path.dirname(path.rstrip('/')) + '/'
    file_entries = [
        f"<li>{get_htmx_link(parent, '..', False) if parent != '/' else ''}</li>"
    ]
    for key in files:
        name, ext = os.path.splitext(key.replace(path, '').rstrip('/'))
        file_entries.append(f'<li>{get_htmx_link(key, name, ext != '')}</li>')
    
    return f"""\
    <ul id="folder" hx-swap-oob="true" hx-boost="true" class="p-4 max-w-md min-w-half">
        {'\n'.join(file_entries)}
    </ul>"""

def get_file_template(content):
    with open("player.html") as player_file:
        player = player_file.read()

    with open("loadPlayer.js") as load_player_file:
        load_player = load_player_file.read()

    return f"""\
    <div
        id="audio" hx-swap-oob="true"
        class="max-w-md flex flex-col items-center gap-2"
        style="min-width:50%"
    >
        <p id="name"></p>

        {player}

        <script id="load-player" hx-preserve type="text/javascript">
        {load_player}
        </script>

        {content}
    </div>
"""

def get_error_content(content):
    return f'<p id="error" class="text-red-600">{content}</p>'

def get_htmx_link(path, text, is_file):
    encoded_path = encode_path_components(path)
    return f"""<a
        href="{URL}/{encoded_path}" hx-push-url="{URL}/{encoded_path}" hx-swap="none"
        {f'hx-on::before-request="trackClicked(\'{os.path.splitext(path)[0]}\')"' if is_file else ''}
        class="cursor-pointer"
    >{text}</a>"""

def music_order(name):
    if '/OP ' in name:
        return (1, name)
    elif '/ED ' in name:
        return (2, name)
    else:
        return (3, name)

def encode_path_components(path):
    """
    Splits a path into its components, quotes each component, and returns
    a list of the quoted components.
    """
    normalized_path = os.path.normpath(path)
    components = normalized_path.split(os.path.sep)
    quoted_components = [urllib.parse.quote(component) for component in components]
    return os.path.sep.join(quoted_components)
