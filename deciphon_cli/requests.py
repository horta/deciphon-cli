from pathlib import Path

import requests
import typer
from requests.exceptions import ConnectionError
from requests_toolbelt.multipart import encoder
from requests_toolbelt.multipart.encoder import MultipartEncoderMonitor
from tqdm import tqdm

from deciphon_cli.errors import handle_connection_error
from deciphon_cli.settings import settings

__all__ = ["get_json", "get_plain", "post", "delete", "upload", "download"]


def url(path: str) -> str:
    return f"{settings.api_url}{path}"


def get(path: str, content_type: str) -> requests.Response:
    hdrs = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "X-API-KEY": settings.api_key,
    }
    try:
        return requests.get(url(path), headers=hdrs)
    except ConnectionError as conn_error:
        handle_connection_error(conn_error)


def pretty_json(v) -> str:
    import json

    return json.dumps(v, indent=2)


def get_json(path: str) -> str:
    return pretty_json(get(path, "application/json").json())


def get_plain(path: str) -> str:
    return get(path, "text/plain").text


def delete(path: str) -> str:
    hdrs = {
        "Accept": "application/json",
        "X-API-KEY": settings.api_key,
    }
    try:
        return pretty_json(requests.delete(url(path), headers=hdrs).json())
    except ConnectionError as conn_error:
        handle_connection_error(conn_error)


def post(path: str, json) -> requests.Response:
    hdrs = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-KEY": settings.api_key,
    }
    try:
        return requests.post(url(path), headers=hdrs, json=json)
    except ConnectionError as conn_error:
        handle_connection_error(conn_error)


def tqdm_file(total_bytes: int, filename: str):
    return tqdm(
        total=total_bytes,
        desc=filename,
        unit_scale=True,
        unit_divisor=1024,
        unit="B",
    )


class UploadProgress:
    def __init__(self, total_bytes: int, filename: str):
        self._bar = tqdm_file(total_bytes, filename)
        self._bytes_read = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        del args
        self._bar.close()

    def __call__(self, monitor: MultipartEncoderMonitor):
        increment = monitor.bytes_read - self._bytes_read
        self._bar.update(increment)
        self._bytes_read += increment


def upload(path: str, field_name: str, filepath: Path, mime: str) -> str:
    e = encoder.MultipartEncoder(
        fields={
            field_name: (
                filepath.name,
                open(filepath, "rb"),
                mime,
            )
        }
    )
    with UploadProgress(e.len, filepath.name) as up:
        monitor = encoder.MultipartEncoderMonitor(e, up)
        hdrs = {
            "Accept": "application/json",
            "Content-Type": monitor.content_type,
            "X-API-KEY": settings.api_key,
        }
        r = requests.post(
            url(path),
            data=monitor,  # type: ignore
            headers=hdrs,
        )
    return pretty_json(r.json())


def download(path: str, filename: str):
    hdrs = {
        "Accept": "*/*",
        "X-API-KEY": settings.api_key,
    }
    with requests.get(url(path), stream=True, headers=hdrs) as r:
        r.raise_for_status()
        with open(filename, "wb") as f:
            total = int(r.headers["Content-Length"])
            with tqdm_file(total, filename) as bar:
                for chunk in r.iter_content(chunk_size=8192):
                    # filter out keep-alive new chunks
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
