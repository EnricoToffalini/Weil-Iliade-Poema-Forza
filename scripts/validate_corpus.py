#!/usr/bin/env python3
"""Controlli sul corpus, sulla struttura editoriale e sullo stato del progetto.

Raccoglie in un solo comando le verifiche che il progetto non può permettersi
di saltare:

* **integrità del francese** — il Markdown e la rappresentazione strutturata
  descrivono lo stesso testo, blocco per blocco; conteggi e ordine tornano; le
  citazioni omeriche non sono state fuse né duplicate; la nota di Simone Weil
  c'è;
* **corrispondenza francese-italiano** — il corpus italiano ricalca esattamente
  la struttura del francese, così che la traduzione possa entrarci un blocco
  per volta;
* **struttura editoriale** — le cesure dichiarate in `site/sezioni.yml` cadono
  fra un blocco e l'altro, mai dentro una citazione, e ogni sezione comincia
  con la prosa;
* **stato della traduzione** — in questa fase l'italiano deve contenere
  soltanto segnaposti espliciti: il controllo esiste per impedire che una bozza
  finisca nel corpus senza che nessuno se ne accorga;
* **pulizia** — nessun residuo del progetto gemello «La Condizione Operaia».

Uso:

    python scripts/validate_corpus.py
    python scripts/validate_corpus.py --consenti-traduzione   # dalla fase 2

L'opzione serve alla fase in cui la traduzione comincerà davvero: allenta il
solo controllo sui segnaposti, lasciando in piedi tutti gli altri.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from corpus import (
    FR_JSON,
    FR_MD,
    IT_MD,
    RADICE,
    SEZIONI,
    TIPI_DA_TRADURRE,
    Blocco,
    ErroreDiCorpus,
    dividi_front_matter,
    dividi_in_sezioni,
    leggi_francese,
    leggi_francese_json,
    leggi_italiano,
    leggi_sezioni,
)

# Conteggi attesi del saggio, fissati sulla fonte consegnata. Se il corpus
# cambia davvero questi numeri vanno aggiornati qui e nel manifest, di
# proposito: non devono poter cambiare per sbaglio.
ATTESI = {"heading": 1, "prose": 139, "verse": 59, "note": 1}

# Residui del progetto di riferimento, «La Condizione Operaia». Si cercano su
# tutti i file di testo del progetto, escluso questo script e la resa in docs/.
RESIDUI = (
    "Condizione Operaia",
    "Condition ouvrière",
    "Condition ouvriere",
    "Weil-Condizione-Operaia",
    "condition_ouvriere",
    "la-condizione-operaia",
    "journal d’usine",
    "Diario di fabbrica",
)
ESTENSIONI_DA_ISPEZIONARE = {".md", ".qmd", ".yml", ".yaml", ".css", ".lua", ".bat", ".txt", ".py"}
CARTELLE_ESCLUSE = {".git", ".quarto", "docs", "__pycache__", ".venv"}


class Esito:
    """Raccoglie gli errori invece di fermarsi al primo."""

    def __init__(self) -> None:
        self.errori: list[str] = []
        self.note: list[str] = []

    def errore(self, messaggio: str) -> None:
        self.errori.append(messaggio)

    def ok(self, messaggio: str) -> None:
        self.note.append(messaggio)


# ---------------------------------------------------------------------------
# controlli


def controlla_francese(esito: Esito) -> list[Blocco] | None:
    try:
        blocchi = leggi_francese()
    except ErroreDiCorpus as errore:
        esito.errore(f"corpus francese: {errore}")
        return None

    conteggio = Counter(b.tipo for b in blocchi)
    if conteggio != Counter(ATTESI):
        esito.errore(
            f"il francese ha {dict(conteggio)} blocchi, attesi {ATTESI}"
        )
    if conteggio.get("note") != 1:
        esito.errore("manca la nota finale di Simone Weil")

    # Ordine e numerazione: gli identificatori devono progredire senza salti,
    # tipo per tipo, nell'ordine in cui i blocchi stanno nel testo.
    contatori: Counter[str] = Counter()
    for blocco in blocchi:
        contatori[blocco.tipo] += 1
        atteso = f"{blocco.id[0]}{contatori[blocco.tipo]:03d}"
        if blocco.id != atteso:
            esito.errore(f"identificatore fuori ordine: {blocco.id}, atteso {atteso}")
            break

    # Le citazioni omeriche: niente righe vuote, nessun verso ripetuto due
    # volte di fila dentro la stessa citazione, nessuna citazione identica a
    # un'altra. Un singolo verso può invece tornare in due citazioni diverse:
    # Simone Weil cita due volte gli stessi versi (il lamento di Briseide in
    # v015 e v048, il pianto di Achille in v020 e v051), e non è un errore.
    citazioni: dict[tuple[str, ...], str] = {}
    for blocco in blocchi:
        if blocco.tipo != "verse":
            continue
        if not blocco.righe or any(not riga.strip() for riga in blocco.righe):
            esito.errore(f"{blocco.id}: la citazione contiene una riga vuota")
        for prima, seconda in zip(blocco.righe, blocco.righe[1:]):
            if prima.strip() and prima.strip() == seconda.strip():
                esito.errore(f"{blocco.id}: il verso «{prima[:40]}» è ripetuto di fila")
        if blocco.righe in citazioni:
            esito.errore(
                f"{blocco.id}: citazione identica a {citazioni[blocco.righe]}"
            )
        citazioni[blocco.righe] = blocco.id

    # Due citazioni consecutive nel corpus sono legittime (v044 e v045 lo sono),
    # ma nessuna deve essersi fusa con l'altra: il conteggio dei versi del
    # Markdown e del JSON è già stato riscontrato da leggi_francese().
    _, dal_json = leggi_francese_json()
    versi_md = sum(len(b.righe) for b in blocchi if b.tipo == "verse")
    versi_json = sum(len(b.righe) for b in dal_json if b.tipo == "verse")
    if versi_md != versi_json:
        esito.errore(f"versi: {versi_md} nel Markdown, {versi_json} nel JSON")
    else:
        esito.ok(f"francese: {len(blocchi)} blocchi, {versi_md} versi citati")

    # Il testo consegnato deve essere rappresentato per intero: nessun blocco
    # perso rispetto al file sorgente.
    _, corpo = dividi_front_matter(FR_MD.read_text(encoding="utf-8"))
    paragrafi = len([p for p in re.split(r"\n[ \t]*\n", corpo) if p.strip()])
    if paragrafi != len(blocchi):
        esito.errore(
            f"{FR_MD.name} ha {paragrafi} paragrafi ma se ne sono letti {len(blocchi)}"
        )
    return blocchi


def controlla_italiano(esito: Esito, francese: list[Blocco]) -> list[Blocco] | None:
    try:
        italiano = leggi_italiano()
    except ErroreDiCorpus as errore:
        esito.errore(f"corpus italiano: {errore}")
        return None

    if len(italiano) != len(francese):
        esito.errore(
            f"il corpus italiano ha {len(italiano)} blocchi, il francese {len(francese)}"
        )
        return italiano
    for it, fr in zip(italiano, francese):
        if (it.id, it.tipo) != (fr.id, fr.tipo):
            esito.errore(
                f"disallineamento: l'italiano ha {it.id}/{it.tipo} dove il "
                f"francese ha {fr.id}/{fr.tipo}"
            )
            return italiano
        if it.tipo == "note" and it.etichetta != fr.etichetta:
            esito.errore(f"{it.id}: etichetta di nota diversa dal francese")
    esito.ok(f"italiano: {len(italiano)} blocchi allineati al francese")
    return italiano


def controlla_traduzione(esito: Esito, italiano: list[Blocco], consentita: bool) -> None:
    traducibili = [b for b in italiano if b.tipo in TIPI_DA_TRADURRE]
    fatti = [b for b in traducibili if not b.e_segnaposto]

    intestazione, _ = dividi_front_matter(IT_MD.read_text(encoding="utf-8"))
    dichiarato = re.search(r"^stato_traduzione:\s*\"?(\w+)\"?", intestazione, re.M)
    stato = dichiarato.group(1) if dichiarato else None
    reale = "tradotto" if not (len(traducibili) - len(fatti)) else "da_tradurre"
    if stato != reale:
        esito.errore(
            f"corpus italiano: `stato_traduzione: {stato}` ma lo stato reale è {reale}"
        )

    if consentita:
        esito.ok(
            f"traduzione: {len(fatti)} di {len(traducibili)} blocchi tradotti"
        )
        return

    if fatti:
        elenco = ", ".join(b.id for b in fatti[:10]) + ("…" if len(fatti) > 10 else "")
        esito.errore(
            f"in questa fase nessun blocco italiano deve contenere traduzione, "
            f"ma {len(fatti)} non sono più segnaposti: {elenco}. "
            "Se la traduzione è cominciata davvero, usare --consenti-traduzione."
        )
    else:
        esito.ok(
            f"traduzione: nessuna prodotta; {len(traducibili)} segnaposti espliciti"
        )


def controlla_sezioni(esito: Esito, francese: list[Blocco]) -> None:
    try:
        sezioni = leggi_sezioni()
        divise = dividi_in_sezioni(francese, sezioni)
    except ErroreDiCorpus as errore:
        esito.errore(f"sezioni editoriali: {errore}")
        return

    if not 8 <= len(sezioni) <= 12:
        esito.errore(f"{len(sezioni)} sezioni: fuori dall'intervallo previsto (8-12)")

    posizioni = {b.id: i for i, b in enumerate(francese)}
    for sezione in sezioni:
        indice = posizioni[sezione["inizio"]]
        blocco = francese[indice]
        if blocco.tipo != "prose":
            esito.errore(
                f"sezione {sezione['numero']}: comincia con {blocco.id} ({blocco.tipo}); "
                "una sezione deve cominciare con un paragrafo di prosa"
            )
        # Una citazione omerica non va mai separata dalla prosa che la
        # introduce: se il blocco precedente è in versi, la cesura cadrebbe
        # dentro la citazione così com'è composta nel testo.
        if indice > 0 and francese[indice - 1].tipo == "verse":
            precedente = francese[indice - 1]
            if precedente.righe[-1].rstrip().endswith((",", ";", ":")):
                esito.errore(
                    f"sezione {sezione['numero']}: la cesura spezza la citazione "
                    f"{precedente.id}"
                )

    # Nessun titolo editoriale tematico: le sezioni non hanno e non devono
    # avere titoli propri. Il solo titolo del corpus è quello del saggio.
    titoli = [b for b in francese if b.tipo == "heading"]
    if len(titoli) != 1:
        esito.errore(f"il testo ha {len(titoli)} titoli: dovrebbe averne uno solo")

    parole = [sum(b.parole for b in sezione) for sezione in divise]
    esito.ok(
        f"sezioni: {len(sezioni)}, da {min(parole)} a {max(parole)} parole "
        f"({sum(parole)} in tutto)"
    )


def controlla_pagine(esito: Esito) -> None:
    """Le pagine generate esistono e corrispondono alle sezioni dichiarate."""
    try:
        sezioni = leggi_sezioni()
    except ErroreDiCorpus:
        return  # già segnalato altrove
    for sezione in sezioni:
        pagina = SEZIONI.parent / f"{sezione['pagina']}.qmd"
        if not pagina.exists():
            esito.errore(f"manca la pagina site/{pagina.name}: lanciare build_site.py")
            continue
        testo = pagina.read_text(encoding="utf-8")
        if f'title: "§ {sezione["numero"]}"' not in testo:
            esito.errore(f"site/{pagina.name}: manca il marcatore «§ {sezione['numero']}»")
        if "toc: false" not in testo:
            esito.errore(f"site/{pagina.name}: l'indice di pagina non è disattivato")

    quarto = SEZIONI.parent / "_quarto.yml"
    if quarto.exists():
        configurazione = quarto.read_text(encoding="utf-8")
        for sezione in sezioni:
            attesa = f'text: "Sezione {sezione["numero"]}"'
            if attesa not in configurazione:
                esito.errore(f"_quarto.yml: manca l'etichetta «Sezione {sezione['numero']}»")
    esito.ok(f"pagine: {len(sezioni)} sezioni generate e dichiarate")


def controlla_pulizia(esito: Esito) -> None:
    questo = Path(__file__).resolve()
    trovati: list[str] = []
    for percorso in RADICE.rglob("*"):
        if not percorso.is_file() or percorso.suffix.lower() not in ESTENSIONI_DA_ISPEZIONARE:
            continue
        if CARTELLE_ESCLUSE & set(percorso.relative_to(RADICE).parts):
            continue
        if percorso.resolve() == questo:
            continue
        testo = percorso.read_text(encoding="utf-8", errors="replace")
        for residuo in RESIDUI:
            if residuo.lower() in testo.lower():
                trovati.append(f"{percorso.relative_to(RADICE).as_posix()}: «{residuo}»")
    if trovati:
        for voce in trovati:
            esito.errore(f"residuo del progetto precedente — {voce}")
    else:
        esito.ok("pulizia: nessun residuo del progetto precedente")


# ---------------------------------------------------------------------------


def main() -> int:
    analizzatore = argparse.ArgumentParser(
        description="Verifica corpus, sezioni editoriali e stato della traduzione"
    )
    analizzatore.add_argument(
        "--consenti-traduzione",
        action="store_true",
        help="ammette blocchi italiani già tradotti (dalla fase 2 in poi)",
    )
    argomenti = analizzatore.parse_args()

    for percorso in (FR_MD, FR_JSON, IT_MD, SEZIONI):
        if not percorso.exists():
            print(f"[errore] manca {percorso.relative_to(RADICE).as_posix()}", file=sys.stderr)
            return 1

    esito = Esito()
    francese = controlla_francese(esito)
    if francese:
        italiano = controlla_italiano(esito, francese)
        if italiano:
            controlla_traduzione(esito, italiano, argomenti.consenti_traduzione)
        controlla_sezioni(esito, francese)
    controlla_pagine(esito)
    controlla_pulizia(esito)

    for nota in esito.note:
        print(f"  ok  {nota}")
    if esito.errori:
        print()
        for errore in esito.errori:
            print(f"[errore] {errore}", file=sys.stderr)
        print(f"\nValidazione fallita: {len(esito.errori)} problemi.", file=sys.stderr)
        return 1
    print("\nValidazione riuscita.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
