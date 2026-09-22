"""OpenDART disclosures → RawItem (official / confirmed-fact path for KR equities)."""

from __future__ import annotations

import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import get_settings
from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider

logger = logging.getLogger(__name__)

_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
_VIEW_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"


class DartProvider(SourceProvider):
    """Fetch recent DART filings for a KRX stock code (6-digit)."""

    name = SourceType.OFFICIAL

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        cache_path: Optional[Path] = None,
        lookback_days: int = 14,
        timeout: float = 20.0,
    ) -> None:
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.dart_api_key).strip()
        self.lookback_days = max(1, int(lookback_days or settings.dart_lookback_days))
        self.timeout = float(timeout)
        default_cache = Path(settings.dart_corp_code_cache_path)
        self.cache_path = Path(cache_path) if cache_path else default_cache
        self._stock_to_corp: dict[str, str] | None = None

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[RawItem]:
        if not self.api_key:
            logger.info("dart skipped reason=no_api_key")
            return []

        stock = (symbol or "").strip().zfill(6) if (symbol or "").strip().isdigit() else ""
        if not stock or len(stock) != 6:
            logger.info("dart skipped reason=bad_symbol symbol=%r", symbol)
            return []

        corp_code = self._corp_code_for_stock(stock)
        if not corp_code:
            logger.warning("dart skipped reason=no_corp_code symbol=%s", stock)
            return []

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=self.lookback_days)
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_no": 1,
            "page_count": min(max(limit, 1), 100),
            "sort": "date",
            "sort_mth": "desc",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(_LIST_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            logger.exception("dart list failed symbol=%s", stock)
            return []

        result = payload.get("result") or payload
        status = str(result.get("status") or "")
        if status not in {"000", "013"}:  # 013 = no data
            logger.warning(
                "dart list status=%s message=%s symbol=%s",
                status,
                result.get("message"),
                stock,
            )
            return []
        if status == "013":
            return []

        rows = result.get("list") or []
        items: list[RawItem] = []
        for row in rows:
            if since_id and str(row.get("rcept_no") or "") <= since_id:
                continue
            item = self._to_raw_item(row, stock_code=stock, company_name=name)
            if item:
                items.append(item)
            if len(items) >= limit:
                break

        logger.info(
            "dart fetch symbol=%s corp=%s fetched=%s",
            stock,
            corp_code,
            len(items),
        )
        return items

    def _to_raw_item(
        self,
        row: dict,
        *,
        stock_code: str,
        company_name: Optional[str],
    ) -> RawItem | None:
        rcept_no = str(row.get("rcept_no") or "").strip()
        report_nm = str(row.get("report_nm") or "").strip()
        if not rcept_no or not report_nm:
            return None

        corp_name = str(row.get("corp_name") or company_name or stock_code).strip()
        rcept_dt = str(row.get("rcept_dt") or "").strip()
        published_at = None
        if len(rcept_dt) == 8 and rcept_dt.isdigit():
            try:
                published_at = datetime(
                    int(rcept_dt[:4]),
                    int(rcept_dt[4:6]),
                    int(rcept_dt[6:8]),
                    tzinfo=timezone.utc,
                ).replace(tzinfo=None)
            except ValueError:
                published_at = None

        url = _VIEW_URL.format(rcp=rcept_no)
        text = (
            f"[DART 공시] {corp_name} ({stock_code})\n"
            f"{report_nm}\n"
            f"접수번호: {rcept_no}\n"
            f"원문: {url}"
        )
        return RawItem(
            provider=SourceType.OFFICIAL,
            external_id=f"dart:{rcept_no}",
            url=url,
            author="DART",
            title=f"{corp_name}: {report_nm}",
            text=text,
            language="ko",
            published_at=published_at,
            raw_payload={
                "source": "opendart",
                "stock_code": stock_code,
                "corp_code": row.get("corp_code"),
                "corp_name": corp_name,
                "report_nm": report_nm,
                "rcept_no": rcept_no,
                "rcept_dt": rcept_dt,
                "pblntf_ty": row.get("pblntf_ty"),
            },
        )

    def _corp_code_for_stock(self, stock_code: str) -> Optional[str]:
        mapping = self._load_corp_map()
        return mapping.get(stock_code)

    def _load_corp_map(self) -> dict[str, str]:
        if self._stock_to_corp is not None:
            return self._stock_to_corp

        if self.cache_path.exists():
            try:
                import json

                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data:
                    self._stock_to_corp = {str(k).zfill(6): str(v) for k, v in data.items()}
                    return self._stock_to_corp
            except Exception:
                logger.warning("dart corp cache read failed path=%s", self.cache_path)

        mapping = self._download_corp_map()
        self._stock_to_corp = mapping
        if mapping:
            try:
                import json

                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(
                    json.dumps(mapping, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                logger.warning("dart corp cache write failed path=%s", self.cache_path)
        return mapping

    def _download_corp_map(self) -> dict[str, str]:
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(_CORP_CODE_URL, params={"crtfc_key": self.api_key})
                resp.raise_for_status()
                raw = resp.content
        except Exception:
            logger.exception("dart corpCode download failed")
            return {}

        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
                if not name:
                    return {}
                xml_bytes = zf.read(name)
        except Exception:
            logger.exception("dart corpCode unzip failed")
            return {}

        mapping: dict[str, str] = {}
        try:
            root = ET.fromstring(xml_bytes)
            for node in root.findall(".//list"):
                stock = (node.findtext("stock_code") or "").strip()
                corp = (node.findtext("corp_code") or "").strip()
                if stock.isdigit() and len(stock) == 6 and corp:
                    mapping[stock] = corp
        except Exception:
            logger.exception("dart corpCode parse failed")
            return {}

        logger.info("dart corpCode loaded stocks=%s", len(mapping))
        return mapping
