#!/usr/bin/env python3
"""Crea lo scheletro del corpus italiano ricalcando la struttura del francese.

Il file prodotto, `corpus/it/iliade-poema-forza.md`, è la sede della futura
traduzione: un blocco per ogni blocco francese, nello stesso ordine, ciascuno
preceduto dal proprio marcatore `<!-- @id tipo -->` e riempito con un
segnaposto esplicito.

Tradurre, in seguito, vorrà dire sostituire il segnaposto con il testo
italiano, senza toccare i marcatori: le cesure editoriali, gli URL delle
pagine e la resa in PDF restano quelli di adesso.

Uso:

    python scripts/build_corpus_it.py            # crea il file se non c'è
    python scripts/build_corpus_it.py --check    # verifica soltanto
    python scripts/build_corpus_it.py --forza    # riscrive, se non c'è traduzione

Il file non viene mai riscritto se contiene già del testo tradotto: in quel
caso lo script si ferma ed elenca i blocchi che perderebbe.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from corpus import (
    IT_MD,
    RADICE,
    TIPI_DA_TRADURRE,
    Blocco,
    ErroreDiCorpus,
    leggi_francese,
    leggi_italiano,
)

TITOLO_IT = "L’Iliade, o il poema della forza"
TITOLO_FR = "L’Iliade ou le poème de la force"

INTESTAZIONE = f"""---
# Scheletro generato da scripts/build_corpus_it.py sulla struttura del testo
# francese. Ogni blocco del corpo porta l'identificatore stabile del blocco
# francese corrispondente: tradurre vuol dire sostituire il segnaposto,
# lasciando il marcatore dov'è. Non aggiungere, non togliere, non riordinare
# i blocchi; fuori dai blocchi non deve esserci altro testo.
title: "{TITOLO_IT}"
title_fr: "{TITOLO_FR}"
author: "Simone Weil"
language: "it"
# `da_tradurre` finché resta anche un solo segnaposto; `tradotto` quando non
# ne resta nessuno. `scripts/validate_corpus.py` verifica che il valore
# corrisponda allo stato reale del file.
stato_traduzione: "da_tradurre"
fonte_fr: "corpus/fr/iliade-poeme-force.md"
---
"""


RIFERIMENTO_NOTA = re.compile(r"\[\^[^\]]+\]")


def richiami(blocco: Blocco) -> str:
    """I richiami di nota (`[^1]`) presenti nel blocco francese.

    Non sono testo da tradurre ma struttura: vanno riportati tali e quali nel
    segnaposto italiano, perché la nota di Simone Weil resti agganciata al
    verso da cui pende. `build_site.py` mette la definizione della nota nella
    stessa pagina in cui compare il richiamo.
    """
    return "".join(RIFERIMENTO_NOTA.findall("\n".join(blocco.righe)))


def segnaposto(blocco: Blocco) -> list[str]:
    """Il contenuto provvisorio di un blocco italiano ancora da tradurre."""
    marcatore = f"<!-- @{blocco.id} {blocco.tipo} -->"
    nome = blocco.id.upper()
    if blocco.tipo == "heading":
        return [marcatore, f"# {TITOLO_IT.upper()}"]
    if blocco.tipo == "verse":
        versi = len(blocco.righe)
        return [
            marcatore,
            f"> [TRADUZIONE ITALIANA — CITAZIONE OMERICA {nome}, "
            f"{versi} {'VERSO' if versi == 1 else 'VERSI'}, DA INSERIRE]"
            + richiami(blocco),
        ]
    if blocco.tipo == "note":
        return [
            marcatore,
            f"[^{blocco.etichetta}]: [TRADUZIONE ITALIANA — NOTA DI SIMONE WEIL "
            f"{nome} DA INSERIRE]",
        ]
    return [
        marcatore,
        f"[TRADUZIONE ITALIANA — BLOCCO {nome} DA INSERIRE]" + richiami(blocco),
    ]


def componi(francese: list[Blocco]) -> str:
    parti = [INTESTAZIONE]
    for blocco in francese:
        parti.append("\n".join(segnaposto(blocco)) + "\n")
    return "\n".join(parti)


def tradotti(percorso: Path) -> list[str]:
    """Gli identificatori dei blocchi italiani che non sono più segnaposti."""
    if not percorso.exists():
        return []
    try:
        return [
            b.id
            for b in leggi_italiano(percorso)
            if b.tipo in TIPI_DA_TRADURRE and not b.e_segnaposto
        ]
    except ErroreDiCorpus:
        # File illeggibile: meglio non sovrascriverlo alla cieca. Lo si
        # segnala come interamente da salvaguardare.
        return ["(file non interpretabile)"]


def main() -> int:
    analizzatore = argparse.ArgumentParser(
        description="Crea lo scheletro di corpus/it/ dalla struttura del francese"
    )
    analizzatore.add_argument(
        "--check",
        action="store_true",
        help="verifica che lo scheletro esista e sia allineato, senza scrivere",
    )
    analizzatore.add_argument(
        "--forza",
        action="store_true",
        help="riscrive lo scheletro esistente (solo se non contiene traduzione)",
    )
    argomenti = analizzatore.parse_args()

    try:
        francese = leggi_francese()
    except ErroreDiCorpus as errore:
        print(f"[errore] corpus francese: {errore}", file=sys.stderr)
        return 1

    atteso = componi(francese)
    relativo = IT_MD.relative_to(RADICE).as_posix()

    if argomenti.check:
        if not IT_MD.exists():
            print(f"[errore] manca {relativo}", file=sys.stderr)
            return 1
        try:
            italiano = leggi_italiano()
        except ErroreDiCorpus as errore:
            print(f"[errore] {relativo}: {errore}", file=sys.stderr)
            return 1
        if [(b.id, b.tipo) for b in italiano] != [(b.id, b.tipo) for b in francese]:
            print(
                f"[errore] {relativo} non ricalca più la struttura del francese",
                file=sys.stderr,
            )
            return 1
        da_tradurre = [b for b in italiano if b.tipo in TIPI_DA_TRADURRE]
        fatti = sum(1 for b in da_tradurre if not b.e_segnaposto)
        print(
            f"{relativo}: {len(italiano)} blocchi, "
            f"{fatti} di {len(da_tradurre)} tradotti"
        )
        return 0

    if IT_MD.exists():
        gia_tradotti = tradotti(IT_MD)
        if gia_tradotti:
            print(
                f"[errore] {relativo} contiene già {len(gia_tradotti)} blocchi "
                "tradotti: " + ", ".join(gia_tradotti[:8])
                + ("…" if len(gia_tradotti) > 8 else ""),
                file=sys.stderr,
            )
            print("Lo scheletro non viene riscritto.", file=sys.stderr)
            return 1
        if not argomenti.forza:
            print(f"{relativo} esiste già ed è tutto da tradurre: usare --forza per rifarlo")
            return 0

    IT_MD.parent.mkdir(parents=True, exist_ok=True)
    IT_MD.write_text(atteso, encoding="utf-8", newline="\n")
    print(f"scritto {relativo}: {len(francese)} blocchi, tutti da tradurre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
