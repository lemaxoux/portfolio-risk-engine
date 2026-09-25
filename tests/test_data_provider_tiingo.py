"""Tests de l'adaptateur Tiingo, sur réponses simulées.

Aucun appel réseau : la session HTTP est remplacée par un double qui rend des
réponses écrites à la main. Les tests passent hors ligne et ne consomment pas
de quota.
"""

from __future__ import annotations

from datetime import date

import pytest
import requests

from backend.data_provider.base import (
    ProviderError,
    RateLimitError,
    UnknownTickerError,
)
from backend.data_provider.tiingo import BASE_URL, TiingoProvider

CLE = "cle-secrete-de-test"


# --------------------------------------------------------------- Doublures --


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, illisible=False):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload
        self._illisible = illisible

    def json(self):
        if self._illisible:
            raise ValueError("réponse non JSON")
        return self._payload


class FakeSession:
    """Rend les réponses de la file ; la dernière est répétée si elle s'épuise.

    Une entrée qui est une exception est levée, ce qui simule une coupure
    réseau au niveau de `requests`.
    """

    def __init__(self, *reponses):
        self.headers = {}
        self.calls = []
        self._file = list(reponses)

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        element = self._file.pop(0) if len(self._file) > 1 else self._file[0]
        if isinstance(element, Exception):
            raise element
        return element


def seance(jour, close=100.0, adj_close=100.0, **extra):
    ligne = {
        "date": f"{jour}T00:00:00.000Z",
        "open": 99.0,
        "high": 101.0,
        "low": 98.0,
        "close": close,
        "adjClose": adj_close,
        "volume": 1_000_000,
        "splitFactor": 1.0,
    }
    ligne.update(extra)
    return ligne


def provider(session, **kwargs):
    kwargs.setdefault("sleep", lambda _: None)  # pas d'attente réelle en test
    kwargs.setdefault("backoff_base", 0.0)
    return TiingoProvider(api_key=CLE, session=session, **kwargs)


# ------------------------------------------------------- Authentification --


def test_le_token_part_en_en_tete():
    session = FakeSession(FakeResponse(payload=[]))
    p = provider(session)
    assert session.headers["Authorization"] == f"Token {CLE}"


def test_le_token_n_apparait_ni_dans_l_url_ni_dans_les_parametres():
    # C'est tout l'intérêt de l'en-tête : les URLs finissent dans les logs, les
    # traces d'exception de requests et l'historique du shell, pas les en-têtes.
    session = FakeSession(FakeResponse(payload=[seance("2026-01-02")]))
    provider(session).get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 3))

    appel = session.calls[0]
    assert CLE not in appel["url"]
    assert CLE not in str(appel["params"])
    assert "token" not in {k.lower() for k in (appel["params"] or {})}


def test_une_cle_absente_est_signalee_clairement(monkeypatch):
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="TIINGO_API_KEY"):
        TiingoProvider(api_key=None, session=FakeSession(FakeResponse()))


# ---------------------------------------------------------------- Endpoints --


def test_l_url_des_prix_est_celle_de_tiingo():
    session = FakeSession(FakeResponse(payload=[]))
    provider(session).get_daily_adjusted("aapl", date(2026, 1, 1), date(2026, 1, 31))

    appel = session.calls[0]
    assert appel["url"] == f"{BASE_URL}/AAPL/prices"
    assert appel["params"]["startDate"] == "2026-01-01"
    assert appel["params"]["endDate"] == "2026-01-31"
    assert appel["timeout"] is not None, "un appel sans timeout peut bloquer le batch"


def test_les_metadonnees_donnent_nom_et_place():
    session = FakeSession(
        FakeResponse(
            payload={
                "ticker": "AAPL",
                "name": "Apple Inc",
                "exchangeCode": "NASDAQ",
                "startDate": "1980-12-12",
            }
        )
    )
    info = provider(session).get_security_info("aapl")

    assert session.calls[0]["url"] == f"{BASE_URL}/AAPL"
    assert (info.ticker, info.name, info.exchange) == ("AAPL", "Apple Inc", "NASDAQ")


# ------------------------------------------------------------------ Parsing --


def test_adj_close_alimente_le_cours_ajuste_et_non_close():
    # Le point qui fausserait tous les rendements s'il était inversé.
    session = FakeSession(
        FakeResponse(payload=[seance("2026-01-02", close=195.0, adj_close=97.5)])
    )
    (bar,) = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 3)
    )

    assert bar.close == 195.0
    assert bar.adj_close == 97.5


def test_la_date_horodatee_devient_une_date_simple():
    session = FakeSession(FakeResponse(payload=[seance("2026-01-02")]))
    (bar,) = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 3)
    )
    assert bar.date == date(2026, 1, 2)


def test_les_seances_sont_rendues_triees():
    session = FakeSession(
        FakeResponse(
            payload=[seance("2026-01-06"), seance("2026-01-02"), seance("2026-01-05")]
        )
    )
    bars = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 7)
    )
    assert [b.date for b in bars] == [
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]


def test_un_adj_close_manquant_echoue_au_lieu_de_passer():
    # Stocker un trou silencieux coûterait plus cher que d'échouer ici.
    session = FakeSession(FakeResponse(payload=[seance("2026-01-02", adjClose=None)]))
    with pytest.raises(ProviderError, match="adjClose"):
        provider(session).get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 3))


def test_le_split_factor_est_remonte():
    session = FakeSession(
        FakeResponse(payload=[seance("2026-01-02", splitFactor=4.0)])
    )
    (bar,) = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 3)
    )
    assert bar.split_factor == 4.0


def test_le_dividende_est_remonte():
    # Sans lui, l'ingestion ne voit pas que Tiingo a réajusté tout
    # l'historique antérieur au détachement.
    session = FakeSession(
        FakeResponse(payload=[seance("2026-09-15", divCash=0.53)])
    )
    (bar,) = provider(session).get_daily_adjusted(
        "KO", date(2026, 9, 15), date(2026, 9, 15)
    )
    assert bar.div_cash == 0.53


def test_une_seance_sans_dividende_porte_zero():
    session = FakeSession(
        FakeResponse(payload=[seance("2026-01-02"), seance("2026-01-05", divCash=None)])
    )
    bars = provider(session).get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 5))
    assert [b.div_cash for b in bars] == [0.0, 0.0]


def test_un_week_end_rend_une_liste_vide_sans_erreur():
    session = FakeSession(FakeResponse(payload=[]))
    assert (
        provider(session).get_daily_adjusted("AAPL", date(2026, 1, 3), date(2026, 1, 4))
        == []
    )


def test_une_fenetre_inversee_n_appelle_pas_l_api():
    # Cas courant au rattrapage quand la base est déjà à jour : ne pas gaspiller
    # un appel sur les 50 de l'heure.
    session = FakeSession(FakeResponse(payload=[]))
    bars = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 10), date(2026, 1, 5)
    )
    assert bars == []
    assert session.calls == []


# ------------------------------------------------------- Erreurs et retries --


def test_un_ticker_inconnu_leve_unknown_ticker_error():
    session = FakeSession(FakeResponse(status_code=404))
    with pytest.raises(UnknownTickerError):
        provider(session).get_security_info("ZZZZ")


def test_un_ticker_inconnu_n_est_pas_reessaye():
    session = FakeSession(FakeResponse(status_code=404))
    with pytest.raises(UnknownTickerError):
        provider(session).get_security_info("ZZZZ")
    assert len(session.calls) == 1


def test_un_429_est_reessaye_puis_aboutit():
    session = FakeSession(
        FakeResponse(status_code=429),
        FakeResponse(payload=[seance("2026-01-02")]),
    )
    bars = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 3)
    )
    assert len(bars) == 1
    assert len(session.calls) == 2


def test_un_429_persistant_leve_rate_limit_error():
    session = FakeSession(FakeResponse(status_code=429))
    with pytest.raises(RateLimitError):
        provider(session, max_attempts=3).get_daily_adjusted(
            "AAPL", date(2026, 1, 1), date(2026, 1, 3)
        )
    assert len(session.calls) == 3, "toutes les tentatives doivent être utilisées"


def test_retry_after_prime_sur_le_backoff():
    attentes = []
    session = FakeSession(
        FakeResponse(status_code=429, headers={"Retry-After": "42"}),
        FakeResponse(payload=[]),
    )
    p = provider(session, sleep=attentes.append, backoff_base=2.0)
    p.get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 3))

    assert attentes == [42.0], "le serveur sait mieux que nous quand revenir"


def test_le_backoff_est_croissant_sans_retry_after():
    attentes = []
    session = FakeSession(FakeResponse(status_code=503))
    p = provider(session, sleep=attentes.append, backoff_base=2.0, max_attempts=4)
    with pytest.raises(ProviderError):
        p.get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 3))

    assert len(attentes) == 3, "une attente entre chaque tentative, pas après la dernière"
    assert attentes == sorted(attentes)


def test_une_coupure_reseau_est_reessayee():
    session = FakeSession(
        requests.ConnectionError("réseau coupé"),
        FakeResponse(payload=[seance("2026-01-02")]),
    )
    bars = provider(session).get_daily_adjusted(
        "AAPL", date(2026, 1, 1), date(2026, 1, 3)
    )
    assert len(bars) == 1


def test_une_coupure_reseau_persistante_leve_provider_error():
    session = FakeSession(requests.Timeout("trop lent"))
    with pytest.raises(ProviderError) as exc:
        provider(session, max_attempts=2).get_daily_adjusted(
            "AAPL", date(2026, 1, 1), date(2026, 1, 3)
        )
    assert not isinstance(exc.value, RateLimitError), "une coupure n'est pas un quota"


def test_une_cle_invalide_n_est_pas_reessayee():
    # 401 : insister ne ferait que brûler du quota pour le même refus.
    session = FakeSession(FakeResponse(status_code=401))
    with pytest.raises(ProviderError, match="401"):
        provider(session).get_security_info("AAPL")
    assert len(session.calls) == 1


def test_une_reponse_illisible_est_signalee():
    session = FakeSession(FakeResponse(illisible=True))
    with pytest.raises(ProviderError):
        provider(session).get_daily_adjusted("AAPL", date(2026, 1, 1), date(2026, 1, 3))
