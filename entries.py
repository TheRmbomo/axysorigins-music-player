import os, re, json
from datetime import datetime
from typing import Any

from env import BUCKET, URL, INDEX, s3_client
from utils import season_map, re_season, get_s3_folder, encode_path_components

display_music_exts = ['.mp3', '.m4a']
arrow_classes = "material-symbols-outlined flex justify-center items-center"
now = datetime.now()
current_year = now.year
if current_year > 2099:
    raise Exception("Unimplemented")
current_year = current_year % 1000 % 100
current_season = (now.month - 1) // 3
period_min = 13*4 + 1
period_max = current_year*4 + current_season

def display_folder_contents(path: str, response) -> str:
    if not (path_match := re.search(r"^[\w_-]+(?:\/(\d{2}-[1-4]))?(?:\/([^/]+))?", path)):
        return ''
 
    season = path_match.group(1)
    show = path_match.group(2)

    file_entries = []

    add_season_navigation(path, file_entries, season, show)
    
    entries: list[str] = []
    entries += [key['Key'] for key in response.get('Contents', [])]
    entries += [folder['Prefix'] for folder in response.get('CommonPrefixes', [])]

    add_season_metadata(entries, file_entries, season, show)

    entries = sorted(entries, key=music_order, reverse=path == INDEX)

    if path + '/' in entries:
        entries.remove(path + '/')

    if path == INDEX:
        all_seasons_dict: dict[int, list[str]] = {}
        other = []
        for key in entries:
            parent = os.path.dirname(key.rstrip('/')) + '/'
            name, ext = os.path.splitext(key.replace(parent, '').rstrip('/'))
            if season_match := re.search(re_season, key):
                year = int(season_match.group(1))
                year_seasons = all_seasons_dict.setdefault(
                    year,
                    ['<li class="flex-1 p-2 bg-slate-700 rounded-md"></li>']*4
                )

                season = int(season_match.group(2))
                entry = entry_element(
                    f'{parent}{name}{ext}', season_map[season], ext != '',
                    liClassName="flex-1",
                )
                year_seasons[(season - 1) % 4] = entry
            else:
                entry = entry_element(f'{parent}{name}{ext}', name, ext != '')
                other.append(entry)

        season_tuples = sorted(all_seasons_dict.items(), reverse=True)
        all_seasons_dict = dict(season_tuples)
        for year in all_seasons_dict:
            seasons = all_seasons_dict[year]
            file_entries.append(f"""\
            <li class="flex gap-2 items-center w-full">
                <div>20{year}</div>
                <ul class="flex-1 flex gap-2 w-full">{'\n'.join(seasons)}</ul>
            </li>""")

        file_entries += other
    else:
        for key in entries:
            # e.g. key = 'folder/subfolder/subfolder/'
            # e.g. key = 'folder/subfolder/subfolder/song.mp3'
            parent = os.path.dirname(key.rstrip('/')) + '/'
            # e.g. parent = 'folder/subfolder' + '/'
            name, ext = os.path.splitext(key.replace(parent, '').rstrip('/'))

            label = re.sub(r"(OP|ED)( \d+)? FULL ", badge(r"\1\2"), name)

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
    >{'\n'.join(file_entries)}</ul>"""

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

def find_season(period: int, d: int) -> str | None:
    while period_min < period < period_max:
        period += d
        year = period // 4
        season = (period % 4) + 1
        season = f'{year}-{season}'
        if get_s3_folder(f'{INDEX}/{season}'):
            return season
    return None

def music_order(name):
    if '/OP ' in name:
        return (1, name)
    elif '/ED ' in name:
        return (2, name)
    else:
        return (3, name)

def add_season_navigation(path: str, file_entries: list[str], season, show):
    previous_season = None
    next_season = None

    if season and not show and (season_match := re.search(re_season, season)):
        period = int(season_match.group(1)) * 4 + (int(season_match.group(2)) - 1) % 4
        previous_season = find_season(period, -1)
        next_season = find_season(period, +1)

    parent = os.path.dirname(path) + '/'

    file_entries.append(
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
    )

def add_season_metadata(entries, file_entries, season, show):
    metadata: dict[str, Any] | None = None
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
        folder_data: dict[str, Any] = metadata.get("folderMetadata", {})
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
