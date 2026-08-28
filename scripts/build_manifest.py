#!/usr/bin/env python3
"""Aggiorna le impronte SHA-256 dei file del corpus in `corpus/manifest.yml`.

Il manifest è scritto a mano: tiene i dati di provenienza (opera, prima
pubblicazione, edizione di riferimento, trascrizione digitale). Le sole voci
che questo script tocca sono le impronte `sha256:` e la data `verificato_il`,
perché sono le uniche che devono seguire i file byte per byte.

Uso:

    python scripts/build_manifest.py            # riscrive le impronte
    python scripts/build_manifest.py --check    # verifica soltanto
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from corpus import CORPUS, FR_JSON, FR_MD, IT_MD, MANIFEST, RADICE, impronta

FILE_DEL_CORPUS = (FR_MD, FR_JSON, IT_MD)
VOCE_SHA = re.compile(r"^(?P<spazi>\s*)sha256:\s*(?P<valore>\S*)\s*$")
VOCE_FILE = re.compile(r"^\s*(?:-\s+)?file:\s*(?P<percorso>\S+)\s*$")
VOCE_DATA = re.compile(r"^(?P<spazi>\s*)verificato_il:\s*\S*\s*$")


def impronte_attese() -> dict[str, str]:
    return {
        percorso.relative_to(RADICE).as_posix(): impronta(percorso)
        for percorso in FILE_DEL_CORPUS
    }


def aggiorna(testo: str, attese: dict[str, str], oggi: str) -> str:
    """Riscrive `sha256:` e `verificato_il:` lasciando intatto tutto il resto."""
    righe = testo.split("\n")
    corrente: str | None = None
    for indice, riga in enumerate(righe):
        trovato_file = VOCE_FILE.match(riga)
        if trovato_file:
            corrente = trovato_file.group("percorso")
            continue
        trovato_sha = VOCE_SHA.match(riga)
        if trovato_sha and corrente in attese:
            righe[indice] = f"{trovato_sha.group('spazi')}sha256: {attese[corrente]}"
            continue
        trovato_data = VOCE_DATA.match(riga)
        if trovato_data:
            righe[indice] = f"{trovato_data.group('spazi')}verificato_il: '{oggi}'"
    return "\n".join(righe)


def main() -> int:
    analizzatore = argparse.ArgumentParser(description="Aggiorna le impronte del corpus")
    analizzatore.add_argument("--check", action="store_true", help="verifica soltanto")
    argomenti = analizzatore.parse_args()

    mancanti = [p for p in FILE_DEL_CORPUS if not p.exists()]
    if mancanti:
        for percorso in mancanti:
            print(f"[errore] manca {percorso.relative_to(RADICE).as_posix()}", file=sys.stderr)
        return 1

    attese = impronte_attese()
    testo = MANIFEST.read_text(encoding="utf-8")
    oggi = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nuovo = aggiorna(testo, attese, oggi)

    if argomenti.check:
        # Si confrontano le sole impronte: `verificato_il` cambia a ogni
        # esecuzione e non dice nulla sull'integrità dei file.
        import yaml

        dati = yaml.safe_load(testo) or {}
        registrate = {
            voce.get("file"): voce.get("sha256")
            for voce in (dati.get("file_del_corpus") or [])
        }
        errori = [
            f"{nome}: atteso {sha[:12]}…, registrato {str(registrate.get(nome))[:12]}…"
            for nome, sha in attese.items()
            if registrate.get(nome) != sha
        ]
        if errori or set(registrate) != set(attese):
            for errore in errori:
                print(f"[errore] {errore}", file=sys.stderr)
            if set(registrate) != set(attese):
                print(
                    "[errore] il manifest non elenca esattamente i file del corpus",
                    file=sys.stderr,
                )
            return 1
        print(f"{MANIFEST.name}: impronte allineate ai {len(attese)} file del corpus")
        return 0

    if nuovo != testo:
        MANIFEST.write_text(nuovo, encoding="utf-8", newline="\n")
        print(f"aggiornato corpus/{MANIFEST.name}")
    else:
        print(f"corpus/{MANIFEST.name} già aggiornato")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
