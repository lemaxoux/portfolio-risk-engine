"""La base du serveur public, lue et contrôlée une fois, au démarrage.

Le serveur public ne sert qu'une base : celle que `python -m
tools.base_serveur` a bâtie, figée à la date du gel, sans aucun portefeuille.
Ce module la désigne, la contrôle, et en retient ce que les routes relisent à
chaque requête sans rouvrir la question : son empreinte, sa date, son
catalogue.

═══ UNE VARIABLE, SANS DÉFAUT ═══

Le chemin vient de `MX_RISK_BASE_DU_SERVEUR`, et de rien d'autre : ni
`MX_RISK_DB_PATH`, ni `data/`. Sans elle, le serveur ne démarre pas. Il ne
peut donc pas ouvrir par mégarde la base d'une application installée.

═══ CE QUI EST REFUSÉ AU DÉMARRAGE ═══

Un serveur qui démarrerait sur une base douteuse répondrait quand même, et
rien dans ses réponses ne le dirait. Chaque contrôle arrête donc le
démarrage :

* le fichier a l'empreinte SHA-256 écrite à côté de lui par l'outil : c'est
  la base qui a été vérifiée, pas une autre ;
* elle ne contient ni portefeuille ni position ;
* chaque titre a des prix, jusqu'à la même dernière séance, et l'indice de
  référence est là ;
* chaque titre a un cours à chaque séance de la base, depuis avant la plus
  ancienne crise du catalogue, et assez de séances pour la fenêtre par
  défaut. La liste des titres est fermée, et tous sont analysables de la
  même façon : aucune composition ne mène à une fenêtre réduite, à une
  couverture partielle, ni aux refus du moteur qui s'y rattachent.

Ces refus s'écrivent dans le journal du serveur. Aucun n'est publié.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.db.lecture_seule import (
    nombre_de_seances,
    ouvrir,
    portefeuilles_en_base,
    seances_par_titre,
)
from backend.risk_engine.config import DEFAULT_BENCHMARK, DEFAULT_WINDOW
from backend.risk_engine.portfolio import Security, latest_price_date, load_securities
from backend.risk_engine.scenarios import SCENARIOS

from .empreinte import empreinte_du_code

VARIABLE_BASE = "MX_RISK_BASE_DU_SERVEUR"
SUFFIXE_DE_L_EMPREINTE = ".sha256"


class BaseRefusee(RuntimeError):
    """La base désignée n'est pas celle qu'un serveur public peut servir."""


@dataclass(frozen=True)
class Base:
    """Ce que le serveur retient de sa base, une fois contrôlée."""

    chemin: Path
    sha256: str
    date_gel: date
    catalogue: tuple[Security, ...]
    code_sha256: str

    @property
    def noms(self) -> dict[str, str]:
        """Le nom de chaque titre, par ticker : celui de la valorisation."""
        return {titre.ticker: titre.name for titre in self.catalogue}


def empreinte_du_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def chemin_designe() -> Path:
    """Le chemin que donne la variable d'environnement. Aucun défaut."""
    designe = os.environ.get(VARIABLE_BASE, "").strip()
    if not designe:
        raise BaseRefusee(
            f"{VARIABLE_BASE} n'est pas définie : le serveur public ne sert que "
            "la base qu'elle désigne, et n'en ouvre aucune autre."
        )
    return Path(designe).expanduser().resolve()


def charger(chemin: Path | None = None) -> Base:
    """Contrôle la base et rend ce que les routes en lisent. Lève
    `BaseRefusee` au premier contrôle qui échoue."""
    chemin = chemin_designe() if chemin is None else chemin.resolve()
    if not chemin.is_file():
        raise BaseRefusee(f"Base du serveur absente : {chemin}")

    temoin = chemin.with_name(chemin.name + SUFFIXE_DE_L_EMPREINTE)
    if not temoin.is_file():
        raise BaseRefusee(f"Empreinte de la base absente : {temoin}")
    attendue = temoin.read_text(encoding="ascii").strip()
    constatee = empreinte_du_fichier(chemin)
    if constatee != attendue:
        raise BaseRefusee(
            f"La base n'a pas l'empreinte écrite à côté d'elle : {constatee} "
            f"au lieu de {attendue}."
        )

    conn = ouvrir(chemin)
    try:
        portefeuilles, positions = portefeuilles_en_base(conn)
        if portefeuilles or positions:
            raise BaseRefusee(
                f"La base contient {portefeuilles} portefeuille(s) et {positions} "
                "position(s) : celle du serveur n'en contient aucun."
            )
        catalogue = tuple(load_securities(conn))
        gel = latest_price_date(conn)
        seances = seances_par_titre(conn)
        seances_de_la_base = nombre_de_seances(conn)
    finally:
        conn.close()

    if not catalogue or gel is None:
        raise BaseRefusee("La base n'a aucun titre, ou aucun prix.")
    sans_prix = [titre.ticker for titre in catalogue if titre.ticker not in seances]
    if sans_prix:
        raise BaseRefusee(f"Titres sans aucun prix : {', '.join(sans_prix)}.")
    if DEFAULT_BENCHMARK not in seances:
        raise BaseRefusee(f"L'indice de référence {DEFAULT_BENCHMARK} n'est pas dans la base.")

    # Autant de séances que la base en compte de distinctes, pour chaque
    # titre : avec la clé (ticker, date), c'est avoir un cours à chacune. Le
    # panel aligné d'une composition, quelle qu'elle soit, est alors la base
    # entière.
    incomplets = sorted(
        ticker for ticker, (nombre, _, _) in seances.items() if nombre != seances_de_la_base
    )
    if incomplets:
        raise BaseRefusee(
            f"Titres sans cours à chaque séance de la base : {', '.join(incomplets)}."
        )
    nombre, debut, fin = seances[DEFAULT_BENCHMARK]
    if fin != gel:
        raise BaseRefusee(f"L'indice s'arrête au {fin}, la base au {gel}.")
    premiere_crise = min(scenario.start for scenario in SCENARIOS)
    if debut > premiere_crise:
        raise BaseRefusee(
            f"L'historique commence le {debut}, après le début de la plus "
            f"ancienne crise du catalogue ({premiere_crise})."
        )
    if nombre <= DEFAULT_WINDOW:
        raise BaseRefusee(
            f"{nombre} séances en base : il en faut plus de {DEFAULT_WINDOW} "
            "pour la fenêtre par défaut."
        )

    return Base(
        chemin=chemin,
        sha256=constatee,
        date_gel=gel,
        catalogue=catalogue,
        code_sha256=empreinte_du_code(),
    )
