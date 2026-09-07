import dataclasses
import enum
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


def download_bulk_file(download_type: BulkDownloadType):
    downloads: list[BulkDownload] = [
        BulkDownload(**download) for download in fetch_json(BULK_DATA)
    ]

    download = next(filter(lambda d: d.type == download_type.value, downloads))

    if download:
        home_path = Path.home()
        config_path = home_path / ".grimoire"
        download_path = config_path / "downloads" / download_type.value
        download_path.mkdir(parents=True, exist_ok=True)
        formatted_updated_at = datetime.fromisoformat(download.updated_at).strftime(
            "%Y%m%dT%H%M%S"
        )
        download_file = download_path / f"{formatted_updated_at}.jsonl.gz"
        with open(download_file, "wb", buffering=False) as file:
            download_json(download.jsonl_download_uri, file)
