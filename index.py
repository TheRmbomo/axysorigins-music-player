import os
from datetime import datetime
from typing import Dict, Any
from enum import Enum
import base64
import urllib.parse
import gzip
import re
import json
from http import cookies

from env import BUCKET, URL, INDEX, IMAGES, s3_client
from router import route

season_map = {"1": "Winter", "2": "Spring", "3": "Summer", "4": "Fall"}
display_music_exts = ['.mp3', '.m4a']
re_season = r"(\d{2})-(1|2|3|4)"

now = datetime.now()
current_year = now.year
if current_year > 2099:
    raise Exception("Unimplemented")
current_year = current_year % 1000 % 100
current_season = (now.month - 1) // 3

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
        season = season_map.get(match.group(2), "")
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
                .replace('ED ', '')\
                .replace('FULL ', '')

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

def get_s3_folder(path):
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=path + '/', Delimiter='/')
        if response['KeyCount'] == 0:
            # Empty / non-existent folder
            return None
        return response
    except:
        return None

def s3_file_exists(path) -> bool:
    try:
        s3_client.head_object(Bucket=BUCKET, Key=path)
        return True
    except:
        return False

arrow_classes = "material-symbols-outlined flex justify-center items-center"

def display_folder_contents(path: str, response) -> str:
    if not (path_match := re.search(r"^[\w_-]+(?:\/(\d{2}-[1-4]))?(?:\/([^/]+))?", path)):
        return ''
 
    season = path_match.group(1)
    show = path_match.group(2)

    previous_season = None
    next_season = None

    if season and not show and (season_match := re.search(re_season, season)):
        period = int(season_match.group(1)) * 4 + (int(season_match.group(2)) - 1) % 4
        previous_season = find_season(period, -1)
        next_season = find_season(period, +1)

    parent = os.path.dirname(path) + '/'

    file_entries = [
        f"""<li><ul class="flex gap-2">
            {entry_element(
                f'{INDEX}/{previous_season}/',
                f"""<strong class="{arrow_classes}" style="transform:translate(3px, -4px) rotate(-90deg)">shift</strong>
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">{previous_season}</span>
                    <span class="text-sm">Previous Season</span>
                </div>""",
                False, liClassName="flex-1"
            ) if previous_season else '<li class="flex-1 p-2"></li>'}

            {entry_element(parent, f'<strong class="flex-1 {arrow_classes}" style="transform:scaleX(1.05) translate(4px, 4px)">shift</strong>', False)\
            if path != INDEX and parent != '/' else '<li class="flex-1 p-2"></li>'}

            {entry_element(
                f'{INDEX}/{next_season}/',
                f"""<div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">{next_season}</span>
                    <span class="text-sm">Next Season</span>
                </div>
                <strong class="{arrow_classes}" style="transform:translate(-3px, 4px) rotate(90deg)">shift</strong>""",
                False, liClassName="flex-1"
            ) if next_season else '<li class="flex-1 p-2"></li>'}
        </ul></li>""",
    ]
    
    entries = []
    entries += [key['Key'] for key in response.get('Contents', [])]
    entries += [folder['Prefix'] for folder in response.get('CommonPrefixes', [])]

    metadata: Dict[str, Any] | None = None
    if (season):
        meta_path_parts = [season]
        if show:
            meta_path_parts.append(show)

        meta_path = os.path.sep.join(meta_path_parts)
        try:
            response = s3_client.get_object(Bucket=BUCKET, Key=f'{INDEX}/{meta_path}/metadata.json')
            metadata_file = response['Body']
            metadata = json.load(metadata_file)
        except Exception:
            pass

    if metadata != None:
        folder_data: Dict[str, Any] = metadata.get("folderMetadata", {})
        if "previousSeason" in folder_data or "nextSeason" in folder_data:
            file_entries.append(f"""\
           <li><ul class="flex gap-2">
                {entry_element(
                f'{INDEX}/{folder_data['previousSeason']}/', f"""\
                <strong class="{arrow_classes}" style="transform:translate(-1px, 1px)">skip_previous</strong>
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Previous Season</span>
                    <span class="text-sm">{folder_data['previousSeason']}</span>
                </div>""",
                False, liClassName="flex-1")\
                if "previousSeason" in folder_data else '<li class="flex-1 p-2"></li>'}

                {entry_element(
                f'{INDEX}/{folder_data['nextSeason']}/', f"""\
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Next Season</span>
                    <span class="text-sm">{folder_data['nextSeason']}</span>
                </div>
                <strong class="{arrow_classes}" style="transform:translate(9px, 1px)">skip_next</strong>""",
                False, liClassName="flex-1")\
                if "nextSeason" in folder_data else '<li class="flex-1 p-2"></li>'}
            </ul></li>""")

        if "previousCour" in folder_data or "nextCour" in folder_data:
            file_entries.append(f"""\
            <li><ul class="flex gap-2">
                {entry_element(
                f'{INDEX}/{folder_data['previousCour']}/', f"""\
                <strong class="{arrow_classes}" style="transform:translateY(1px)">arrow_back_2</strong>
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Previous Cour</span>
                    <span class="text-sm">{folder_data['previousCour']}</span>
                </div>""",
                False, liClassName="flex-1")\
                if "previousCour" in folder_data else '<li class="flex-1 p-2"></li>'}

                {entry_element(
                f'{INDEX}/{folder_data['nextCour']}/', f"""\
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Next Cour</span>
                    <span class="text-sm">{folder_data['nextCour']}</span>
                </div>
                <strong class="{arrow_classes}" style="transform:translate(8px, 1px)">play_arrow</strong>""",
                False, liClassName="flex-1")\
                if "nextCour" in folder_data else '<li class="flex-1 p-2"></li>'}
            </ul></li>""")

        if "previousSplitCour" in folder_data or "nextSplitCour" in folder_data:
            file_entries.append(f"""\
            <li><ul class="flex gap-2">
                {entry_element(
                f'{INDEX}/{folder_data['previousSplitCour']}/', f"""\
                <strong class="{arrow_classes}" style="transform:translate(1px, 1px)">fast_rewind</strong>
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Previous Split Cour</span>
                    <span class="text-sm">{folder_data['previousSplitCour']}</span>
                </div>""",
                False, liClassName="flex-1")\
                if "previousSplitCour" in folder_data else '<li class="flex-1 p-2"></li>'}

                {entry_element(
                f'{INDEX}/{folder_data['nextSplitCour']}/', f"""\
                <div class="flex-1 flex flex-col text-left">
                    <span class="text-xs">Next Split Cour</span>
                    <span class="text-sm">{folder_data['nextSplitCour']}</span>
                </div>
                <strong class="{arrow_classes}" style="transform:translate(9px, 1px)">fast_forward</strong>""",
                False, liClassName="flex-1")\
                if "nextSplitCour" in folder_data else '<li class="flex-1 p-2"></li>'}
            </ul></li>""")

        for song_path in metadata.get("addSongs", []):
            entries.append(f'{INDEX}/{song_path}')

    entries = sorted(entries, key=music_order, reverse=path == INDEX)

    if path + '/' in entries:
        entries.remove(path + '/')

    for key in entries:
        # e.g. key = 'folder/subfolder/subfolder/'
        # e.g. key = 'folder/subfolder/subfolder/song.mp3'
        parent = os.path.dirname(key.rstrip('/')) + '/'
        # e.g. parent = 'folder/subfolder' + '/'
        name, ext = os.path.splitext(key.replace(parent, '').rstrip('/'))

        label = name\
            .replace('OP FULL ', badge('OP'))\
            .replace('ED FULL ', badge('ED'))

        if ext != '' and ext not in display_music_exts:
            continue

        entry = entry_element(f'{parent}{name}{ext}', label, ext != '')
        file_entries.append(entry)
    
    return f"""\
    <p id="folder-name" hx-swap-oob="true">{
       (path.rstrip('/') + '/').replace(f'{INDEX}/', '').rstrip('/')
    }</p>
    <ul
        id="folder" hx-swap-oob="true" hx-boost="true"
       class="flex flex-col gap-2 p-2 w-screen md:max-w-md"
    >
        {'\n'.join(file_entries)}
    </ul>"""

def badge(text):
    return f'<span class="inline-block p-1 rounded-sm bg-slate-700 leading-none">{text}</span>'

def entry_element(path, label, is_file, liClassName: str = ''):
    encoded_path = encode_path_components(path)
    return f"""\
    <li class="flex gap-2 bg-slate-700 p-2 rounded-md{f' {liClassName}' if liClassName else ''}">
        <a
            href="{URL}/{encoded_path}"
            {f'hx-push-url="{URL}/{encoded_path}"' if not is_file else ''}
            hx-swap="none"
            {f'hx-on::before-request="trackClicked(\'{
                os.path.splitext(path)[0].replace(f'{INDEX}/', '')
            }\')"' if is_file else ''}
            class="flex-1 flex gap-2 justify-center items-center bg-slate-600 rounded-md p-1 px-2 hover:bg-slate-500 focus:bg-slate-500
            cursor-pointer"
        >{label}</a>
        {f"""<button
            class="flex justify-center items-center
            bg-slate-600 rounded-md active:bg-slate-500 transition-all"
            style="padding:0.125rem;min-width:2.5rem;min-height:2.5rem"
        >
            <span
                data-display="flex"
                class="material-symbols-outlined flex justify-center items-center"
                style="display:none;min-height:2rem"
            >playlist_add</span>
        </button>""" if is_file else ''}
    </li>"""

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

def music_order(name):
    if '/OP ' in name:
        return (1, name)
    elif '/ED ' in name:
        return (2, name)
    else:
        return (3, name)

def encode_path_components(path: str):
    """
    Splits a path into its components, quotes each component, and returns
    a list of the quoted components.
    """
    is_folder = path.endswith('/')
    normalized_path = os.path.normpath(path)
    components = normalized_path.split(os.path.sep)
    quoted_components = [urllib.parse.quote(component) for component in components]
    return os.path.sep.join(quoted_components) + ('/' if is_folder else '')

period_min = 13*4 + 1
period_max = current_year*4 + current_season
def find_season(period: int, d: int) -> str | None:
    while period_min < period < period_max:
        period += d
        year = period // 4
        season = (period % 4) + 1
        season = f'{year}-{season}'
        if get_s3_folder(f'{INDEX}/{season}'):
            return season
    return None
