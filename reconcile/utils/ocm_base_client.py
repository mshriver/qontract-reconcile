import logging
from collections.abc import (
    Generator,
    Mapping,
)
from typing import (
    Any,
    Optional,
    Protocol,
)

from pydantic import BaseModel
from requests import (
    Session,
    codes,
)
from sretoolbox.utils import retry

from reconcile.utils.secret_reader import (
    HasSecret,
    SecretReaderBase,
)

REQUEST_TIMEOUT_SEC = 60


class OCMBaseClient:
    """
    Thin client for OCM. This class takes care of authentication
    and provides methods for GET, POST, PATCH, DELETE to interact with ocm API.
    """

    def __init__(
        self,
        url: str,
        access_token_client_secret: str,
        access_token_url: str,
        access_token_client_id: str,
        session: Optional[Session] = None,
    ):
        self._access_token_client_secret = access_token_client_secret
        self._access_token_client_id = access_token_client_id
        self._access_token_url = access_token_url
        self._url = url
        self._session = session if session else Session()
        self._init_access_token()
        self._init_request_headers()

    @retry()
    def _init_access_token(self):
        data = {
            "grant_type": "client_credentials",
            "client_id": self._access_token_client_id,
            "client_secret": self._access_token_client_secret,
        }
        r = self._session.post(
            self._access_token_url, data=data, timeout=REQUEST_TIMEOUT_SEC
        )
        r.raise_for_status()
        self._access_token = r.json().get("access_token")

    def _init_request_headers(self):
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._access_token}",
                "accept": "application/json",
            }
        )

    def get(self, api_path: str, params: Optional[Mapping[str, str]] = None) -> Any:
        r = self._session.get(
            f"{self._url}{api_path}",
            params=params,
            timeout=REQUEST_TIMEOUT_SEC,
        )
        r.raise_for_status()
        return r.json()

    def get_paginated(
        self,
        api_path: str,
        params: Optional[dict[str, Any]] = None,
        max_page_size: int = 100,
        max_pages: Optional[int] = None,
    ) -> Generator[dict[str, Any], None, None]:
        if not params:
            params_copy = {}
        else:
            params_copy = params.copy()
        params_copy["size"] = max_page_size

        # fetch pages
        records_seen = 0
        while True:
            rs = self.get(api_path, params=params)
            for item in rs.get("items", []):
                yield item
            total_records = rs.get("total", 0)
            current_page = rs.get("page", 0)
            records_on_page = rs.get("size", len(rs.get("items", [])))
            records_seen += records_on_page
            if total_records > records_seen and (
                max_pages and max_pages < current_page
            ):
                # more page available
                params_copy["page"] = current_page + 1
            else:
                return

    def post(
        self,
        api_path: str,
        data: Optional[Mapping[str, Any]] = None,
        params: Optional[Mapping[str, str]] = None,
    ) -> Any:
        r = self._session.post(
            f"{self._url}{api_path}",
            json=data,
            params=params,
            timeout=REQUEST_TIMEOUT_SEC,
        )
        try:
            r.raise_for_status()
        except Exception as e:
            logging.error(r.text)
            raise e
        if r.status_code == codes.no_content:
            return {}
        return r.json()

    def patch(
        self,
        api_path: str,
        data: Mapping[str, Any],
        params: Optional[Mapping[str, str]] = None,
    ):
        r = self._session.patch(
            f"{self._url}{api_path}",
            json=data,
            params=params,
            timeout=REQUEST_TIMEOUT_SEC,
        )
        try:
            r.raise_for_status()
        except Exception as e:
            logging.error(r.text)
            raise e

    def delete(self, api_path: str):
        r = self._session.delete(f"{self._url}{api_path}", timeout=REQUEST_TIMEOUT_SEC)
        r.raise_for_status()


class OCMAPIClientConfigurationProtocol(Protocol):
    url: str
    access_token_client_id: str
    access_token_url: str

    @property
    def access_token_client_secret(self) -> HasSecret:
        ...


class OCMAPIClientConfiguration(BaseModel, arbitrary_types_allowed=True):
    url: str
    access_token_client_id: str
    access_token_url: str
    access_token_client_secret: HasSecret


def init_ocm_base_client(
    cfg: OCMAPIClientConfigurationProtocol,
    secret_reader: SecretReaderBase,
    session: Optional[Session] = None,
) -> OCMBaseClient:
    """
    Initiate an API client towards an OCM instance.
    """
    return OCMBaseClient(
        url=cfg.url,
        access_token_client_secret=secret_reader.read_secret(
            cfg.access_token_client_secret
        ),
        access_token_url=cfg.access_token_url,
        access_token_client_id=cfg.access_token_client_id,
        session=session,
    )
