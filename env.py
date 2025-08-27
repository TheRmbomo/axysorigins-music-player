import os
import boto3

s3_client = boto3.client('s3')

BUCKET = os.getenv('PLAYER_BUCKET', '') # e.g. player-files
URL = os.getenv('PLAYER_URL', '').rstrip('/') # e.g. https://example-website.com/player
INDEX = os.getenv('PLAYER_INDEX', '').lstrip('/').rstrip('/') # e.g. index
IMAGES = os.getenv('PLAYER_IMAGES', '').rstrip('/') # e.g. https://example-website.com/images
