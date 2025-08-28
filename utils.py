import os.path, urllib.parse

from env import BUCKET, s3_client

season_map = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Fall"}
re_season = r"(\d{2})-(1|2|3|4)"

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
