"""Adaptateur Tiingo — seul module du projet qui connaît cette API.

Tout ce qui est spécifique au fournisseur est confiné ici : URLs, noms de
champs JSON, forme de l'authentification, codes d'erreur HTTP. Le reste du
projet ne voit que `DailyBar`, `SecurityInfo` et les erreurs de `base`.
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import date, datetime
from typing import Any, Callable

import requests
from dotenv import load_dotenv

from .base import (
    DailyBar,
    ProviderError,
    RateLimitError,
    SecurityInfo,
    UnknownTickerError,
)

logger = logging.getLogger(__name__)

load_dotenv()

BASE_URL = "https://api.tiingo.com/tiingo/daily"

# Plan gratuit Tiingo. Ces valeurs ne sont pas appliquées côté client (une
# rafale de quelques dizaines d'appels reste dans le budget horaire) ; elles
# documentent la limite que le backoff sur 429 sert à absorber.
FREE_TIER_CALLS_PER_HOUR = 50
FREE_TIER_CALLS_PER_DAY = 1000

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class TiingoProvider:
    """Implémente `MarketDataProvider` au-dessus de l'API Tiingo.

    Le token part dans l'en-tête `Authorization`, jamais en paramètre d'URL :
    les URLs se retrouvent dans les logs, les traces d'erreur et les messages
    d'exception de `requests`, pas les en-têtes.
    """

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        *,
        max_attempts: int = 4,
        backoff_base: float = 2.0,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.getenv("TIINGO_API_KEY")
        if not key:
            raise ProviderError(
                "TIINGO_API_KEY absente. Copier .env.example en .env et y "
                "renseigner la clé (https://api.tiingo.com/account/api/token)."
            )
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token {key}",
                "Content-Type": "application/json",
            }
        )
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._timeout = timeout
        self._sleep = sleep

    # ---------------------------------------------------------------- HTTP --

    def _backoff_delay(self, attempt: int, retry_after: str | None) -> float:
        """Délai avant la tentative suivante.

        `Retry-After` prime quand le serveur l'envoie : il sait mieux que nous
        quand le quota se libère. Sinon backoff exponentiel, avec un bruit
        aléatoire pour éviter que plusieurs appels repartis après une coupure
        ne se resynchronisent sur la même seconde.
        """
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return self._backoff_base**attempt + random.uniform(0, 1)

    def _retry_or_fail(self, path: str, cause: str, attempt: int, retry_after: str | None) -> None:
        delay = self._backoff_delay(attempt, retry_after)
        logger.warning(
            "%s : %s, nouvelle tentative dans %.1fs (%d/%d)",
            path,
            cause,
            delay,
            attempt + 1,
            self._max_attempts,
        )
        self._sleep(delay)

    def _request(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        last_error = ""

        for attempt in range(self._max_attempts):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                last_error = f"erreur réseau ({exc.__class__.__name__})"
                if attempt == self._max_attempts - 1:
                    break
                self._retry_or_fail(path, last_error, attempt, None)
                continue

            status = response.status_code

            if status == 404:
                raise UnknownTickerError(f"Ticker inconnu chez Tiingo : {path}")

            if status in _RETRYABLE_STATUS:
                last_error = f"HTTP {status}"
                if attempt == self._max_attempts - 1:
                    break
                self._retry_or_fail(
                    path, last_error, attempt, response.headers.get("Retry-After")
                )
                continue

            if status >= 400:
                # 401/403 : clé invalide ou plan insuffisant. Réessayer ne
                # ferait que consommer du quota pour le même refus.
                raise ProviderError(f"Tiingo a répondu HTTP {status} sur {path}")

            try:
                return response.json()
            except ValueError as exc:
                raise ProviderError(f"Réponse Tiingo illisible sur {path}") from exc

        message = (
            f"Tiingo injoignable après {self._max_attempts} tentatives sur "
            f"{path} (dernière cause : {last_error})"
        )
        logger.error(message)
        if last_error == "HTTP 429":
            raise RateLimitError(message)
        raise ProviderError(message)

    # ------------------------------------------------------------ Interface --

    def get_security_info(self, ticker: str) -> SecurityInfo:
        payload = self._request(f"/{ticker.upper()}")
        if not isinstance(payload, dict) or not payload.get("ticker"):
            raise UnknownTickerError(f"Métadonnées Tiingo vides pour {ticker}")
        return SecurityInfo(
            ticker=str(payload["ticker"]).upper(),
            name=str(payload.get("name") or ticker).strip(),
            exchange=payload.get("exchangeCode"),
        )

    def get_daily_adjusted(self, ticker: str, start: date, end: date) -> list[DailyBar]:
        if start > end:
            # Arrive quand la base est déjà à jour : pas d'appel, pas de quota.
            logger.debug("%s : fenêtre vide (%s > %s), aucun appel", ticker, start, end)
            return []

        payload = self._request(
            f"/{ticker.upper()}/prices",
            {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "format": "json",
            },
        )
        if not isinstance(payload, list):
            raise ProviderError(
                f"Réponse de prix inattendue pour {ticker} : {type(payload).__name__}"
            )

        bars = sorted((_to_bar(ticker, row) for row in payload), key=lambda b: b.date)
        logger.info(
            "%s : %d séances récupérées (%s → %s)", ticker.upper(), len(bars), start, end
        )
        return bars


# ------------------------------------------------------------------ Parsing --


def _to_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _to_bar(ticker: str, row: Any) -> DailyBar:
    """Traduit une ligne de la réponse Tiingo en `DailyBar`.

    `adjClose` est obligatoire : c'est la seule colonne qui alimente les
    rendements. Une séance sans cours ajusté est une donnée corrompue, pas une
    donnée partielle — mieux vaut échouer que stocker un trou silencieux.
    """
    if not isinstance(row, dict):
        raise ProviderError(f"Séance illisible pour {ticker} : {row!r}")

    try:
        raw_date = str(row["date"])
        parsed_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
    except (KeyError, ValueError) as exc:
        raise ProviderError(f"Date illisible pour {ticker} : {row!r}") from exc

    for champ in ("close", "adjClose"):
        if row.get(champ) is None:
            raise ProviderError(
                f"{ticker} {parsed_date} : champ '{champ}' manquant chez Tiingo"
            )

    volume = row.get("volume")
    return DailyBar(
        date=parsed_date,
        open=_to_float(row.get("open")),
        high=_to_float(row.get("high")),
        low=_to_float(row.get("low")),
        close=float(row["close"]),
        adj_close=float(row["adjClose"]),
        volume=None if volume is None else int(volume),
        split_factor=float(row.get("splitFactor") or 1.0),
    )
