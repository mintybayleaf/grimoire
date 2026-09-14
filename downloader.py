import dataclasses
import enum
import gzip
import json
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Final

import requests

BASE_URI: Final[str] = "https://api.scryfall.com"
BULK_DATA: Final[str] = f"{BASE_URI}/bulk-data"
HEADERS: Final[dict[str, str]] = {"User-Agent": "Grimoire/1.0", "Accept": "*/*"}
CHUNK_SIZE: Final[int] = 128 * 1024  # 128KB


def check_and_raise(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        if error.response:
            raise RuntimeError(
                f"error fetching {error.response.url} with http status {error.response.status_code}"
            )


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS)
    check_and_raise(response)
    return response.json()["data"]


def download_json(url: str, destination: BinaryIO) -> None:
    with requests.get(url, headers=HEADERS, stream=True) as response:
        check_and_raise(response)

        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                destination.write(chunk)


class BulkDownloadType(enum.Enum):
    oracle_cards = "oracle_cards"
    unique_artwork = "unique_artwork"
    default_cards = "default_cards"
    all_cards = "all_cards"
    rulings = "rulings"
    art_tags = "art_tags"
    oracle_tags = "oracle_tags"


@dataclasses.dataclass(frozen=True, slots=True)
class BulkDownload:
    object: str
    id: str
    type: BulkDownloadType
    updated_at: str
    uri: str
    name: str
    description: str
    jsonl_download_uri: str
    compressed_size: int


def get_download_path_for_type(download_type: BulkDownloadType):
    home_path = Path.home()
    config_path = home_path / ".grimoire"
    download_path = config_path / "downloads" / download_type.value
    return download_path


def to_file_timestamp(timestamp: str) -> int:
    return int(datetime.fromisoformat(timestamp).timestamp())


def timestamp_from_file(file: Path) -> int:
    file_name = file.name
    index = file.name.index(".")
    return int(file_name[:index])


def download_bulk_file(download_type: BulkDownloadType):
    downloads: list[BulkDownload] = [
        BulkDownload(**download) for download in fetch_json(BULK_DATA)
    ]

    download = next(filter(lambda d: d.type == download_type.value, downloads))

    if download:
        download_path = get_download_path_for_type(download_type)
        download_path.mkdir(parents=True, exist_ok=True)
        timestamp = to_file_timestamp(download.updated_at)
        download_file = download_path / f"{timestamp}.jsonl.gz"
        with open(download_file, "wb", buffering=False) as file:
            download_json(download.jsonl_download_uri, file)


@dataclasses.dataclass(frozen=True, slots=True)
class MagicCard:
    id: str
    name: str


def stream_latest_for_download_type(download_type: BulkDownloadType) -> Generator[str]:
    download_path = get_download_path_for_type(download_type)
    files = sorted(
        (timestamp_from_file(file) for file in download_path.glob("*.jsonl.gz")),
        reverse=True,
    )
    if files:
        timestamp = files[0]
        with gzip.open(
            download_path / Path(f"{timestamp}.jsonl.gz"), "rt", encoding="utf-8"
        ) as file:
            yield from file


def stream_latest_magic_cards(download_type: BulkDownloadType) -> Generator[MagicCard]:
    for line in stream_latest_for_download_type(download_type):
        data = json.loads(line.strip())
        yield MagicCard(id=data["id"], name=data["name"])
