import os.path
import base64
import boto3
import urllib.parse
import gzip
import re

from botocore.exceptions import ClientError
from enum import Enum

s3_client = boto3.client('s3')
season_map = {"1": "Winter", "2": "Spring", "3": "Summer", "4": "Fall"}

BUCKET = os.getenv('PLAYER_BUCKET') # e.g. player-files
URL = os.getenv('PLAYER_URL', '').rstrip('/') # e.g. https://example-website.com/player
INDEX = os.getenv('PLAYER_INDEX', '').lstrip('/').rstrip('/') # e.g. index
IMAGES = os.getenv('PLAYER_IMAGES', '').rstrip('/') # e.g. https://example-website.com/images

class ItemType(Enum):
    UNKNOWN = 0
    FOLDER = 1
    FILE = 2

def handler(event, _):
    if BUCKET == '':
        return {"statusCode": 500, "body": "PLAYER_BUCKET is missing."}
    if URL == '':
        return {"statusCode": 500, "body": "PLAYER_URL is missing."}
    if INDEX == '':
        return {"statusCode": 500, "body": "PLAYER_INDEX is missing."}
    if IMAGES == '':
        return {"statusCode": 500, "body": "PLAYER_IMAGES is missing."}

    path = urllib.parse.unquote(event['pathParameters']['proxy'])
    headers = event.get('headers') or {}

    HX_REQUEST = (
        headers.get('Hx-Request')
        or headers.get('HX-Request')
        or headers.get('hx-request')
    ) == 'true' and (
        headers.get('Hx-History-Restore-Request')
        or headers.get('HX-History-Restore-Request')
        or headers.get('hx-history-restore-request')
    ) is None

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

    status = 204

    hx_fragment = ""
    full_body = ""

    meta = {
        'name': "Seasons Music",
        'description': "A personal music player.",
        'logo': f"{IMAGES}/logo-small-a.png",
        'url': f'{URL}/{path}',
    }

    match item_type:
        case ItemType.FOLDER:
            folder = os.path.basename(path)

            match = re.match(r"(\d{1,2})-(1|2|3|4)", folder)
            if match:
                year = "20" + match.group(1)
                season = season_map.get(match.group(2), "")
                meta['name'] = f"{year} {season} | Seasons Music"
                meta['description'] = f"Some anime music from the {year} {season} season"
            elif folder != INDEX:
                meta['name'] = f"{folder} | Seasons Music"

            folder_content = f"""\
            <title id="title" hx-swap-oob="true">{meta['name']}</title>
            {display_folder_contents(path, response)}"""

            status = 200
            hx_fragment = folder_content
            full_body = (
                get_file_template("", "")
                + '<script id="load-music" type="text/javascript"></script>'
                + folder_content
                + get_error_content("")
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
            parent_folder_content = ""
            error = ""

            try:
                parent_folder_content = display_folder_contents(parent, get_s3_folder(BUCKET, parent))
            except:
                error = "Failed to list parent folder."

            full_name = os.path.splitext(path)[0]
            full_name_escaped = full_name.replace("'", "\\'")
            meta['name'] = f"{os.path.basename(full_name)} | Seasons Music"

            load_music = f"""\
            <script id="load-music" hx-swap-oob="true" type="text/javascript">
            async function loadMusic() {{
                if (window.url === '{url}') return

                nameElement = document.getElementById('name')
                if (controller) {{
                    console.warn(`Abort ${{nameElement.innerText}}`)
                    controller.abort()
                    controller = null
                }}

                window.url = '{url}'
                console.log('set url', window.url)
                nameElement.innerText = '{full_name_escaped}'
                
                {'loadPlayer()' if HX_REQUEST else ''}
            }}
            loadMusic()
            </script>"""

            status = 200
            hx_fragment = load_music
            full_body = (
                f'<title id="title" hx-swap-oob="true">{meta['name']}</title>'
                + get_file_template(
                    full_name,
                    f"""\
                    <button
                        id="load-button" onclick="loadPlayer()"
                        class="bg-red-600 p-2 rounded-md"
                    >Click to start loading</button>"""
                )
                + load_music
                + parent_folder_content
                + get_error_content(error)
            )
        # case _:
        #     status = 404
        #     full_body = "Failed to find file."
    
    body = hx_fragment if HX_REQUEST else get_html_page(meta, full_body)
    # Remove leading spaces on each line
    body = '\n'.join([line.lstrip() for line in body.splitlines()])

    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "text/html",
            "Vary": "Hx-Request",
            "Content-Encoding": "gzip",
        },
        "isBase64Encoded": True,
        "body": base64.b64encode(gzip.compress(body.encode('utf-8'))).decode('utf-8'),
    }

def get_s3_folder(bucket_name, path):
    path = path.lstrip('/').rstrip('/') + '/'
    return s3_client.list_objects_v2(Bucket=bucket_name, Prefix=path, Delimiter='/')

def get_s3_file(bucket_name, path):
    return s3_client.get_object(Bucket=bucket_name, Key=path)

def get_html_page(meta, content):
    return f"""\
    <!DOCTYPE html>
    <html>
    <head>
        <title id="title">{meta['name']}</title>
        <link rel="icon" type="image/png" href="{meta['logo']}">

        <meta property="og:title" content="{meta['name']}"/>
        <meta property="og:description" content="{meta['description']}"/>
        <meta property="og:image" content="{meta['logo']}"/>
        <meta property="og:url" content="{meta['url']}"/>
        <meta property="og:type" content="music.playlist"/>

        <meta name="twitter:card" content="summary"/>
        <meta name="twitter:title" content="{meta['name']}"/>
        <meta name="twitter:description" content="{meta['description']}"/>
        <meta name="twitter:image" content="{meta['logo']}"/>

        <meta charset="UTF-8"/>
        <meta name="theme-color" content="#6dbcff">

        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <meta name="color-scheme" content="dark light">

        <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.6/dist/htmx.min.js" integrity="sha384-Akqfrbj/HpNVo8k11SXBb6TlBWmXXlYQrCSqEWmyKJe+hDm3Z/B2WVG4smwBkRVm" crossorigin="anonymous"></script>
        <!-- <script src="https://cdnjs.cloudflare.com/ajax/libs/hyperscript/0.9.14/_hyperscript.min.js"></script> -->

        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"/>
        <style>
        :root {{
            --color-slate-500: oklch(55.4% 0.046 257.417);
            --color-slate-600: oklch(44.6% 0.043 257.281);
        }}
        
        .max-w-md {{ max-width: 28rem }}
        .min-w-half {{ min-width: 50% }}
        .bg-slate-500 {{ background-color: var(--color-slate-500) }}
        .bg-slate-600 {{ background-color: var(--color-slate-600) }}

        button:disabled {{ pointer: auto }}
        </style>
    </head>
    <body id="body" hx-preserve class="flex flex-col gap-2 items-center h-screen w-screen m-0 p-2">
        <script type="text/javascript">
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        let nameElement = null, url = '', source = null, audioBuffer = null,
            start = 0, offset = 0,
            animationFrameId = null,
            playing = false, looping = false
        </script>

        {content}
    </body>
    </html>"""

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

def get_file_template(name, content):
    return f"""\
    <div
        id="audio" hx-swap-oob="true"
        class="max-w-md flex flex-col items-center gap-2"
        style="min-width:50%"
    >
        <p id="name">{name}</p>

        <div
            id="player"
            class="w-full flex flex-col gap-2 p-2 bg-slate-500 rounded-md select-none"
            style="touch-action:none"
        >
            <div class="flex gap-2 items-center">
                <div id="timeline" class="flex-1 mx-2 relative h-2 bg-slate-600 rounded-md" style="cursor:pointer">
                    <div id="progress-bar" class="h-full bg-blue-500 rounded-md" style="width:0"></div>
                    <div
                        id="position-indicator" class="absolute rounded-full bg-blue-300"
                        style="
                        width:1rem;height:1rem;left:0;top:50%;margin-left:-0.5rem;transform:translateY(-50%);
                        cursor:grab;"
                    ></div>
                </div>
                <div id="current-time">0:00 / 0:00</div>
            </div>

            <div id="player-controls" class="flex gap-2 items-center invisible">
                <button
                    id="play" disabled
                    onclick="togglePlay()"
                    class="material-symbols-outlined rounded-full p-1"
                    style="outline:none"
                >play_arrow</button>

                <span class="flex-1 inline-block"></span>

                <button
                    id="loop" disabled hx-preserve
                    onclick="toggleLoop()"
                    class="material-symbols-outlined rounded-full p-1"
                    style="outline:none"
                >autorenew</button>

                <!-- <button
                    id="download" disabled
                    class="material-symbols-outlined rounded-full p-1"
                    style="outline:none"
                >download</button> -->
            </div>
        </div>

        <div id="cover-art"></div>

        <script id="load-player" hx-preserve type="text/javascript">
        const timeline = document.getElementById('timeline')
        const progressBar = document.getElementById('progress-bar')
        const positionIndicator = document.getElementById('position-indicator')
        const currentTimeDisplay = document.getElementById('current-time')

        const controls = document.getElementById('player-controls')
        const playButton = document.getElementById('play')
        const loopButton = document.getElementById('loop')
        // const downloadButton = document.getElementById('download')

        document.fonts.ready.then(() => {{
            controls.classList.remove('invisible')
        }})

        let controller = null

        async function loadPlayer() {{
            if (!window.url) return console.error('no url')

            const loadButton = document.getElementById('load-button')
            if (loadButton) loadButton.remove()

            const currentName = nameElement.innerText
            
            playing = false
            pending = true
            
            resetPlayback()
            updatePlayButton()

            if (source) await closeSource()

            controller = new AbortController()
            console.log('loading', currentName)
            await fetch(window.url, {{signal: controller.signal}})
                .then(response => response.arrayBuffer())
                .then(arrayBuffer => {{
                    return audioContext.decodeAudioData(arrayBuffer)
                }})
                .then(async (buffer) => {{
                    console.log('buffer loaded')

                    audioBuffer = buffer

                    playButton.disabled = false
                    loopButton.disabled = false
                    // downloadButton.disabled = false

                    updateTimelineDisplay()

                    pending = false

                    offset = 0
                    await play()
                }})
                .catch((e) => {{
                    if (e.name === 'AbortError') {{
                        console.error('Aborted', currentName)
                        return
                    }}
                    
                    console.error(e)
                    const error = document.getElementById('error')
                    error.innerText = e.message
                }})
        }}

        function togglePlay() {{
            if (playing) {{
                pause()
            }} else {{
                play()
            }}
        }}

        let pending = false
        let resolveSourceEnded = null

        async function closeSource() {{
            const hasEnded = new Promise((res) => resolveSourceEnded = res)
            source.stop()
            // console.log('waiting for ended')
            await hasEnded.catch(console.error)
            // console.log('source closed')
        }}

        async function endSource() {{
            // console.log('source ended')
            source.disconnect()
            source = null
            resolveSourceEnded && resolveSourceEnded()

            if (pending) {{
                playing = false
                cancelAnimationFrame(animationFrameId)
            }} else if (looping) {{
                offset = 0
                await play()
            }}

            updatePlayButton()
        }}

        async function play() {{
            if (source) return console.warn('play / source exists')

            if (pending) return console.warn('play / pending')
            pending = true

            // console.log('play / was playing:', playing)

            if (audioContext.state === 'suspended') {{
                await audioContext.resume()
            }}

            start = audioContext.currentTime - offset
            source = audioContext.createBufferSource()
            source.buffer = audioBuffer
            source.connect(audioContext.destination)
            source.onended = endSource

            source.start(0, offset)
            playing = true

            updateTimeline()
            updatePlayButton()
            pending = false
        }}

        async function pause() {{
            if (pending) return
            pending = true

            // console.log('pause / source:', !!source)

            if (source) await closeSource()
            
            offset = audioContext.currentTime - start
            pending = false
        }}

        async function seekAudio(seekTime) {{
            if (!audioBuffer) return

            const wasPlaying = playing
            console.log('seek / wasPlaying:', wasPlaying)

            if (wasPlaying) await pause()
            offset = seekTime

            if (wasPlaying) {{
                await play()
            }} else {{
                console.log('seek / update timeline display')
                updateTimelineDisplay()
                updatePlayButton()
            }}
        }}

        function updatePlayButton() {{
            // console.log('update play button / playing:', playing)
            if (playing) playButton.innerText = 'pause'
            else playButton.innerText = 'play_arrow'
        }}

        function updateTimeline() {{
            if (!source || !playing || !audioBuffer) return

            offset = audioContext.currentTime - start
            updateTimelineDisplay()
            animationFrameId = requestAnimationFrame(updateTimeline)
        }}

        function updateTimelineDisplay() {{
            if (!audioBuffer) return
            
            const currentMinutes = Math.floor(offset / 60)
            const currentSeconds = Math.floor(offset % 60).toString().padStart(2, '0')

            const durationMinutes = Math.floor(audioBuffer.duration / 60)
            const durationSeconds = Math.floor(audioBuffer.duration % 60).toString().padStart(2, '0')

            currentTimeDisplay.textContent = `${{currentMinutes}}:${{currentSeconds}} / ${{durationMinutes}}:${{durationSeconds}}`
            
            const progress = (offset / audioBuffer.duration) * 100
            progressBar.style.width = `${{progress}}%`
            positionIndicator.style.left = `${{progress}}%`;
        }}

        function resetPlayback() {{
            offset = 0
            progressBar.style.width = '0%'
            positionIndicator.style.left = '0%'
            updateTimelineDisplay()
        }}

        function toggleLoop() {{
            if (looping) {{
                looping = false
                loopButton.classList.remove('text-black', 'bg-white')
            }} else {{
                looping = true
                loopButton.classList.add('text-black', 'bg-white')
            }}
        }}

        timeline.addEventListener('pointerdown', (event) => {{
            if (!audioBuffer) return
            
            const timelineWidth = timeline.offsetWidth
            const clickX = event.offsetX
            const seekTime = (clickX / timelineWidth) * audioBuffer.duration
            seekAudio(seekTime)
        }})

        // Drag functionality for the position indicator
        positionIndicator.addEventListener('pointerdown', (e) => {{
            e.stopPropagation()
            if (!audioBuffer) return
            
            const wasPlaying = playing
            const paused = pause()

            const onMouseMove = (event) => {{
                const timelineRect = timeline.getBoundingClientRect()
                let newX = event.clientX - timelineRect.left

                // Clamp the position within the timeline bounds
                if (newX < 0) newX = 0
                if (newX > timelineRect.width) newX = timelineRect.width

                const seekTime = (newX / timelineRect.width) * audioBuffer.duration
                offset = seekTime
                updateTimelineDisplay()
            }}

            const onMouseUp = async () => {{
                document.removeEventListener('pointermove', onMouseMove)
                document.removeEventListener('pointerup', onMouseUp)

                await paused
                if (wasPlaying) {{
                    await play()
                }} else {{
                    updateTimelineDisplay()
                }}
            }}

            document.addEventListener('pointermove', onMouseMove)
            document.addEventListener('pointerup', onMouseUp)
        }})
        </script>

        {content}
    </div>"""

def get_error_content(content):
    return f'<p id="error" class="text-red-600">{content}</p>'

def get_htmx_link(url, text, _):
    url = quote_path_components(url)
    # {'hx-on::before-request=""' if is_file else ''}
    return f"""<a
        href="{URL}/{url}" hx-push-url="{URL}/{url}" hx-swap="none"
        class="cursor-pointer"
    >{text}</a>"""

def music_order(name):
    if '/OP ' in name:
        return (1, name)
    elif '/ED ' in name:
        return (2, name)
    else:
        return (3, name)

def quote_path_components(path):
    """
    Splits a path into its components, quotes each component, and returns
    a list of the quoted components.
    """
    normalized_path = os.path.normpath(path)
    components = normalized_path.split(os.path.sep)
    quoted_components = [urllib.parse.quote(component) for component in components]
    return os.path.sep.join(quoted_components)
