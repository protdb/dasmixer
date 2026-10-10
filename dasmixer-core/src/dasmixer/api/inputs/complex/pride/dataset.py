import gzip
import os
import shutil
from pathlib import Path

from dasmixer.api.config import get_pxd_temp_dir
from dasmixer.utils.exceptions import DasmixerException, DasmixerNetworkException
from pridepy.download.client import Client
from pridepy.project.project import Project
from requests.exceptions import ConnectionError


class PrideDatasetNotFoundException(DasmixerException):
    pass

class PrideFile:
    dataset_id: str
    name: str
    extension: str
    _compressed: bool = False
    _client: Client
    def __init__(self, client: Client | None, item: dict):
        self.dataset_id = item["projectAccessions"][0]
        self.name = item["fileName"]
        if not self.name.endswith(".gz"):
            self.extension = self.name.split(".")[-1].lower()
        else:
            self.extension = self.name[:-3].split(".")[-1].lower()
            self._compressed = True
        if client is not None:
            self._client = client
        else:
            self._client = Client()

    @property
    def stem(self) -> str:
        max_split = 2 if self._compressed else 1
        return self.name.rsplit('.', maxsplit=max_split)[0]



    def download_file(self) -> Path:
        dataset_path = get_pxd_temp_dir() / self.dataset_id
        file_path = dataset_path / self.name
        self._client.download_file_by_name(
            self.dataset_id,
            self.name,
            str(dataset_path),
            skip_if_downloaded_already=True,
            protocol='ftp',
            username=None,
            password=None,
            aspera_maximum_bandwidth=None,
            checksum_check=True
        )
        if os.path.exists(file_path):
            if self._compressed:
                target_path = file_path.parent / file_path.name[:-3]
                with gzip.open(file_path, 'rb') as f_in, open(target_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                return target_path
            return file_path
        else:
            raise DasmixerException(f'Error downloading file {self.name} from {self.dataset_id}')



class PrideDataset:
    id: str
    _client: Client
    _project: Project
    _metadata: dict
    _files: list[PrideFile]
    allowed_ident_extensions: list[str]
    allowed_spectra_extensions: list[str]
    title: str | None = None
    description: str | None = None

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self._client = Client()
        self._project = Project()
        self.allowed_spectra_extensions = ['mgf']
        self.allowed_ident_extensions = ['mztab']
        self.allowed_fasta_extensions = ['fasta']
        try:
            self._metadata = self._project.search_by_keywords_and_filters(
                keyword=dataset_id, query_filter="", page_size=1, page=0, sort_direction="DESC", sort_fields="accession"
            )[0]
        except IndexError:
            raise PrideDatasetNotFoundException(f'{dataset_id} not found in PRIDE')
        except ConnectionError as e:
            raise DasmixerNetworkException(f'Cannot connect to PRIDE database because of {e}')
        self.title = self._metadata.get("title", 'dataset title not found')
        self.description = self._metadata.get("projectDescription", 'dataset description not found')
        files = self._client.get_all_category_file_list(
            self.dataset_id, categories=['PEAK', 'SEARCH', 'RESULT', 'FASTA', 'OTHER']
        )
        self._files = [PrideFile(self._client, x) for x in files]

    @property
    def spectra_files(self) -> list[PrideFile]:
        return [x for x in self._files if x.extension in self.allowed_spectra_extensions]

    @property
    def ident_files(self) -> list[PrideFile]:
        return [x for x in self._files if x.extension in self.allowed_ident_extensions]

    @property
    def fasta_files(self) -> list[PrideFile]:
        return [x for x in self._files if x.extension in self.allowed_fasta_extensions]