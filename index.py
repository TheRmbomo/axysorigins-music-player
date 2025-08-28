import os
from enum import Enum
import base64
import urllib.parse
import gzip
import re
from http import cookies

from env import BUCKET, URL, INDEX, IMAGES, s3_client
from router import route
from utils import season_map, re_season, s3_file_exists, get_s3_folder
from entries import display_folder_contents

class ItemType(Enum):
    UNKNOWN = 0
    FOLDER = 1
    FILE = 2

def handler(event, _):
    print(event)

    # AWS Gateway or Lambda seem to strip trailing slashes already, but this is explicit redundancy to be safe
    path = urllib.parse.unquote(event['pathParameters']['proxy']).lstrip('/').rstrip('/')

    response = route(event, path)
    if response != None:
        return response

    if BUCKET == '':
        return {"statusCode": 500, "body": "PLAYER_BUCKET is missing."}
    if URL == '':
        return {"statusCode": 500, "body": "PLAYER_URL is missing."}
    if INDEX == '':
        return {"statusCode": 500, "body": "PLAYER_INDEX is missing."}
    if IMAGES == '':
        return {"statusCode": 500, "body": "PLAYER_IMAGES is missing."}

    request_headers = event.get('headers') or {}
    request_headers = {k.lower(): v for k, v in request_headers.items()}

    cookie = request_headers.get('cookie') or ''
    C = cookies.SimpleCookie()
    C.load(cookie)

    HX_REQUEST = request_headers.get('hx-request') == 'true' and request_headers.get('hx-history-restore-request') != 'true'

    item_type = ItemType.UNKNOWN
    response = None

    if s3_file_exists(path):
        item_type = ItemType.FILE

    else:
        if not (response := get_s3_folder(path)):
            return {"statusCode": 404, "body": "Failed to find file."}
        item_type = ItemType.FOLDER

    parent_folder_content = ""
    error = ""

    title = "Seasons Music"
    description = "A personal music player."
    logo = f"{IMAGES}/logo-small-a.png"
    url = f'{URL}/{path}'

    basename = os.path.basename(path)
    match = re.match(re_season, path)
    if match:
        year = "20" + match.group(1)
        season = season_map.get(int(match.group(2)), "")
        title = f"{year} {season} | Seasons Music"
        description = f"Some anime music from the {year} {season} season"

    match item_type:
        case ItemType.FOLDER:
            if basename != INDEX:
                title = f"{basename} | Seasons Music"

            print(path)
            print(response)

            hx_fragment = f"""\
            <title id="title" hx-swap-oob="true">{title}</title>
            {display_folder_contents(path, response)}"""

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

            parent = os.path.dirname(path)

            if (parent_folder := get_s3_folder(parent)):
                parent_folder_content = display_folder_contents(parent, parent_folder)
            else:
                error = "Failed to list parent folder."

            path_name = os.path.splitext(path)[0]
            name = os.path.basename(path_name)\
                .replace('OP ', '')\
                .replace('ED ', '')
            name = re.sub(r"(\d+ )?FULL ", '', name)

            title = f"{name} | Seasons Music"

            with open('loadMusic.js') as load_music_file:
                load_music = load_music_file.read()

            hx_fragment = f"""\
            <title id="title" hx-swap-oob="true">{title}</title>
            <script id="load-music" hx-swap-oob="true" type="text/javascript">
                {load_music\
                    .replace("{{ url }}", url.replace("'", "\\'"))
                    .replace("{{ path }}", path_name.replace("'", "\\'").replace(f'{INDEX}/', ''))
                    .replace("{{ name }}", name)
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

    if signed_in:
        hx_fragment += f"""\
        <script id="reveal-icons" hx-swap-oob="true" type="text/javascript">
        // document.fonts.ready did not work
        document.fonts.onloadingdone = revealIcons 
        </script>"""
        # Client-side loading metadata. Needed?
        # hx_fragment += f"""<script
        #    src="{URL}/metadata/{path.replace(f'{INDEX}/', '')}" type="text/javascript"
        # ></script>"""

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
        playlist = ""
        load_playlist = ""
        if signed_in:
            with open("index.css") as css_file:
                css = css_file.read()
            with open("playlist.html") as playlist_file:
                playlist = playlist_file.read()
            with open("loadPlaylist.js") as load_playlist_file:
                load_playlist = f'<script id="load-playlist-tabs">{load_playlist_file.read()}</script>'

        body = index\
            .replace('{{ title }}', title)\
            .replace('{{ logo }}', logo)\
            .replace('{{ description }}', description)\
            .replace('{{ url }}', url)\
            .replace('{{ css }}', css)

        if signed_in:
            body = body.replace('{{ content }}', (
                audio
                + hx_fragment
                + parent_folder_content
                + playlist
                + load_playlist
                + get_error_content(error)
            ))
        else:
            with open('password.html') as password_file:
                password = password_file.read()
            body = body.replace('{{ content }}', password.replace('{{ url }}', URL))

    # Remove leading spaces on each line
    body = '\n'.join([line.lstrip() for line in body.splitlines()])

    response_headers = {}
    response_headers['Content-Type'] = 'text/html'
    response_headers['Vary'] = 'Hx-Request'

    # Temporary
    response_headers['Cache-Control'] = 'no-store'
    response_headers['Pragma'] = 'no-cache'
    response_headers['Expire'] = 0

    accept_encodings = [e.strip().split(';')[0] for e in request_headers.get('accept-encoding', '').split(',')]
    if 'gzip' in accept_encodings:
        response_headers['Content-Encoding'] = 'gzip'
        body = base64.b64encode(gzip.compress(body.encode('utf-8'))).decode('utf-8')

    return {
        "statusCode": status,
        "headers": response_headers,
        "isBase64Encoded": True,
        "body": body,
    }

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
        {content}

        <script id="load-player" hx-preserve type="text/javascript">
        {load_player}
        </script>
    </div>
"""

def get_error_content(content):
    return f'<p id="error" class="text-red-600">{content}</p>'
