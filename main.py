#!/bin/env/python3
import logging
import os
from time import sleep

import ffmpeg
import requests

# Define config variables
DOWNLOADS_PATH = os.environ.get('EP_DOWNLOADS_PATH', 'downloads/')
WAIT_TIME = int(os.environ.get('EP_WAIT_TIME', 5))
API_TOKEN = os.environ.get('EP_API_TOKEN')
API_HOST = os.environ.get('EP_API_HOST', 'https://easypodcasts.live/api')
API_ENDPOINT_NEXT = f"{API_HOST}/next"
API_ENDPOINT_CONVERTED = f"{API_HOST}/converted"
API_ENDPOINT_CANCEL = f"{API_HOST}/cancel"
# define logging level
LOG_LEVEL = os.environ.get('EP_LOG_LEVEL', 'WARNING')
date_strftime_format = "%y/%m/%d %H:%M:%S"
message_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.WARNING),
                    format=message_format,
                    datefmt=date_strftime_format)

# define API client
api_client = requests.Session()
api_client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
podcasts_client_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                             'Chrome/39.0.2171.95 Safari/537.36 '


class EpApiError(Exception):
    pass


def _get_episode_filename(episode_id):
    return f'episode_{episode_id}.opus'


def _get_episode_path(episode_id):
    return os.path.join(DOWNLOADS_PATH, _get_episode_filename(episode_id))


def get_next_episode():
    logging.info('Getting new episode data')
    response = api_client.get(API_ENDPOINT_NEXT)
    if response.status_code == 200:
        data = response.json()
        logging.info(f'Got new episode data: {data}')
        return data
    else:
        raise EpApiError(
            f'EP API returned not ok status code "{response.status_code}" for {API_ENDPOINT_NEXT} endpoint')


def cancel_episode(episode_id):
    logging.info(f'Canceling episode {episode_id}')
    response = api_client.post(API_ENDPOINT_CANCEL, data={'id': episode_id})
    if response.status_code == 200:
        logging.info(f'Canceled episode {episode_id}')
        return response.json()
    else:
        raise EpApiError(
            f'EP API returned not ok status code "{response.status_code}" for {API_ENDPOINT_CANCEL} endpoint')


def convert_episode(episode_id, episode_url):
    logging.info(f'Converting episode {episode_id} {episode_url}')
    stream = ffmpeg.input(episode_url, user_agent=podcasts_client_user_agent)
    stream = stream.output(_get_episode_path(episode_id),
                           ac='1',
                           acodec='libopus',
                           audio_bitrate='24k',
                           apply_phase_inv='0',
                           frame_duration='60',
                           application='voip'
                           )
    output = ffmpeg.run(stream)
    logging.info(f'Converted episode {episode_id} {episode_url}')
    return output


def upload_converted_episode(episode_id):
    logging.info(f'Uploading converted episode {episode_id}')
    episode_path = _get_episode_path(episode_id)
    response = api_client.post(API_ENDPOINT_CONVERTED,
                               data={'id': episode_id},
                               files={'audio': open(episode_path, 'rb')})
    if str(response.status_code).startswith('2'):
        logging.info(f'Uploaded converted episode {episode_id}')
        return response.json()
    else:
        raise EpApiError(
            f'EP API returned not ok status code "{response.status_code}" for {API_ENDPOINT_CONVERTED} endpoint')


def clean(episode_id):
    logging.info(f'Removing episode {episode_id} file')
    episode_path = _get_episode_path(episode_id)
    os.path.exists(episode_path) and os.remove(episode_path)
    logging.info(f'Removed episode {episode_id} file')


if __name__ == '__main__':
    logging.info(f'Starting Easy Podcasts runner using {WAIT_TIME} seconds loop')

    if not API_TOKEN:
        logging.error('EP API token is not defined. Use EP_API_TOKEN environment variable')
        exit(1)

    if not os.path.exists(DOWNLOADS_PATH):
        logging.info(f'Creating downloads directory {DOWNLOADS_PATH}')
        os.makedirs(DOWNLOADS_PATH)
        logging.info(f'Created downloads directory {DOWNLOADS_PATH}')

    while True:
        episode_data = get_next_episode()

        if episode_data and episode_data != 'noop':
            episode_id = episode_data.get('id')
            episode_url = episode_data.get('url')
            success = False
            try:
                convert_episode(episode_id, episode_url)
                upload_converted_episode(episode_id)
                clean(episode_id)
                success = True
            except Exception as err:
                logging.error(f'Error processing episode {episode_data}. Error: {err}')
            if not success:
                try:
                    cancel_episode(episode_id)
                except Exception as err:
                    logging.error(f'Error canceling episode {episode_data}. Error: {err}')

        sleep(WAIT_TIME)
