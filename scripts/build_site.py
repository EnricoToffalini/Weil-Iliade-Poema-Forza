#!/usr/bin/env python3
"""Genera le pagine Quarto delle sezioni a partire da `corpus/it/`.

Il corpus resta la sola fonte: questo script non lo modifica mai. Taglia il
saggio nei punti dichiarati in `site/sezioni.yml` e scrive una pagina per
sezione, `site/sezione-N.qmd`.

Le pagine sono generate, non redatte: quando la traduzione italiana arriverà
nel corpus basterà rilanciare lo script perché il sito e il PDF la prendano.
Nessun testo viene mai duplicato a mano.

Distinzione voluta fra le due rese:

* nel sito la sezione è una pagina a sé, con URL `sezione-N.html`, indicata
  nella barra laterale come «Sezione N» (etichetta dichiarata in `_quarto.yml`)
  e segnata in pagina dal solo marcatore discreto «§ N»;
* nel PDF il saggio torna continuo: `site/_filtri/struttura-pdf.lua` toglie i
  marcatori «§ N», e con essi i cambi di pagina che li accompagnerebbero.

Uso:

    python scripts/build_site.py            # rigenera site/sezione-*.qmd
    python scripts/build_site.py --check    # verifica soltanto, senza scrivere
"""

from __future__ import annotations

import argparse
import re
import sys

from corpus import (
    RADICE,
    SITO,
    TIPI_DA_TRADURRE,
    Blocco,
    ErroreDiCorpus,
    dividi_in_sezioni,
    leggi_italiano,
    leggi_sezioni,
)

TITOLO_OPERA = "L’Iliade, o il poema della forza"
RIFERIMENTO_NOTA = re.compile(r"\[\^([^\]]+)\]")

INTESTAZIONE_GENERATA = (
    "<!-- Pagina generata da scripts/build_site.py a partire da\n"
    "     corpus/it/iliade-poema-forza.md e da site/sezioni.yml.\n"
    "     Non modificare a mano: le correzioni vanno fatte nel corpus. -->"
)


def cita_yaml(valore: str) -> str:
    return '"' + valore.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rendi_blocco(blocco: Blocco) -> str:
    """Rende un blocco del corpus in Markdown, senza toccarne il testo."""
    if blocco.tipo == "verse":
        # Due spazi in coda: sono gli a-capo forzati che tengono i versi di
        # Omero uno per riga, nel sito come nel PDF. L'ultimo verso non ne ha
        # bisogno, e con essi finirebbe per aprire una riga vuota.
        righe = [f"> {riga}  " for riga in blocco.righe[:-1]]
        righe.append(f"> {blocco.righe[-1]}")
        return "\n".join(righe)
    if blocco.tipo == "note":
        return f"[^{blocco.etichetta}]: " + "\n".join(blocco.righe)
    return "\n".join(blocco.righe)


def descrizione(numero: int, totale: int, da_tradurre: int) -> str:
    stato = (
        "Il testo italiano di questa sezione è in corso di inserimento."
        if da_tradurre
        else "Testo integrale della sezione nella traduzione italiana."
    )
    return (
        f"Sezione {numero} di {totale} di «{TITOLO_OPERA}» di Simone Weil "
        f"(«L’Iliade ou le poème de la force», 1940-1941). {stato}"
    )


def avviso(numero: int, da_tradurre: int, totali: int) -> str:
    """Il cartello che dichiara la sezione ancora da tradurre.

    Deve essere impossibile scambiare per testo definitivo quello che sta
    sotto: il cartello lo dice a parole, i segnaposti dei singoli blocchi lo
    ripetono uno per uno.
    """
    quanti = (
        "tutti i blocchi di questa sezione attendono"
        if da_tradurre == totali
        else f"{da_tradurre} blocchi su {totali} di questa sezione attendono"
    )
    # Solo HTML: nel PDF il saggio è continuo, e dieci cartelli intercalati
    # rimetterebbero sotto gli occhi proprio le divisioni che lì non devono
    # vedersi. Nel PDF a dire quel che manca bastano i segnaposti dei singoli
    # blocchi, che restano.
    # I due riquadri restano annidati e non uniti in uno solo: mettendo
    # `.segnaposto` e `.content-visible` sullo stesso Div, Quarto consuma il
    # blocco condizionale e con esso la classe che gli dà la veste.
    return (
        ':::: {.content-visible when-format="html"}\n'
        "::: {.segnaposto}\n"
        f"**[TRADUZIONE ITALIANA — SEZIONE {numero} DA INSERIRE]**\n\n"
        f"Il testo italiano è in corso di inserimento: {quanti} "
        "ancora il loro testo. Ogni segnaposto qui sotto corrisponde a un paragrafo "
        "o a una citazione omerica dell'originale francese, che è già acquisito "
        "e strutturato nel corpus del progetto.\n"
        ":::\n"
        "::::"
    )


def componi(numero: int, totale: int, blocchi: list[Blocco], note: list[Blocco]) -> str:
    """Il sorgente Quarto di una sezione."""
    # Il titolo del saggio non entra nel corpo: nel sito è il titolo del libro,
    # nel PDF sta in copertina. Le definizioni delle note escono di qui e
    # rientrano subito sotto, nella pagina dove compare il loro richiamo: in
    # HTML ogni sezione è un documento a sé, e una nota definita in un'altra
    # pagina resterebbe irrisolta.
    corpo = [rendi_blocco(b) for b in blocchi if b.tipo not in ("heading", "note")]
    corpo += [rendi_blocco(n) for n in note]

    traducibili = [b for b in blocchi if b.tipo in TIPI_DA_TRADURRE]
    mancanti = [b for b in traducibili if b.e_segnaposto]
    if mancanti:
        corpo.insert(0, avviso(numero, len(mancanti), len(traducibili)))

    testa = (
        "---\n"
        # Titolo della pagina: il marcatore editoriale discreto. L'etichetta
        # leggibile della barra laterale («Sezione N») è dichiarata accanto al
        # file in site/_quarto.yml.
        f"title: {cita_yaml(f'§ {numero}')}\n"
        # Quarto accoda da sé il titolo del libro: qui basta l'etichetta
        # leggibile, altrimenti il titolo della scheda lo ripeterebbe due volte.
        f"pagetitle: {cita_yaml(f'Sezione {numero}')}\n"
        f"description: {cita_yaml(descrizione(numero, totale, len(mancanti)))}\n"
        "format:\n"
        "  html:\n"
        "    # La sezione non ha titoli interni: un indice di pagina sarebbe vuoto.\n"
        "    toc: false\n"
        "    # Distingue in CSS le pagine di sezione: il loro titolo è il\n"
        "    # marcatore «§ N» e va reso in piccolo, non come titolo di capitolo.\n"
        "    body-classes: pagina-sezione\n"
        "---\n\n"
        f"{INTESTAZIONE_GENERATA}\n"
    )
    return testa + "\n" + "\n\n".join(corpo) + "\n"


def raccogli_note(sezioni_di_blocchi: list[list[Blocco]]) -> list[list[Blocco]]:
    """Assegna ogni definizione di nota alla sezione che ne porta il richiamo.

    Nel corpus la nota di Simone Weil sta in fondo al saggio, com'è nella
    stampa; nel sito la sua definizione deve stare nella pagina della citazione
    a cui si aggancia.
    """
    definizioni = {
        b.etichetta: b
        for sezione in sezioni_di_blocchi
        for b in sezione
        if b.tipo == "note"
    }
    per_sezione: list[list[Blocco]] = [[] for _ in sezioni_di_blocchi]
    collocate: set[str] = set()

    for indice, sezione in enumerate(sezioni_di_blocchi):
        for blocco in sezione:
            if blocco.tipo == "note":
                continue
            for etichetta in RIFERIMENTO_NOTA.findall("\n".join(blocco.righe)):
                if etichetta in definizioni and etichetta not in collocate:
                    per_sezione[indice].append(definizioni[etichetta])
                    collocate.add(etichetta)

    orfane = sorted(set(definizioni) - collocate)
    if orfane:
        raise ErroreDiCorpus(
            "nessun richiamo nel testo italiano per le note: " + ", ".join(orfane)
        )
    return per_sezione


def main() -> int:
    analizzatore = argparse.ArgumentParser(
        description="Genera site/sezione-*.qmd da corpus/it/ e site/sezioni.yml"
    )
    analizzatore.add_argument(
        "--check",
        action="store_true",
        help="verifica che le pagine siano allineate al corpus, senza scrivere",
    )
    argomenti = analizzatore.parse_args()

    try:
        italiano = leggi_italiano()
        sezioni = leggi_sezioni()
        divise = dividi_in_sezioni(italiano, sezioni)
        note = raccogli_note(divise)
    except ErroreDiCorpus as errore:
        print(f"[errore] {errore}", file=sys.stderr)
        return 1

    attesi: set[str] = set()
    disallineate: list[str] = []

    for sezione, blocchi, note_di_sezione in zip(sezioni, divise, note):
        contenuto = componi(sezione["numero"], len(sezioni), blocchi, note_di_sezione)
        destinazione = SITO / f"{sezione['pagina']}.qmd"
        attesi.add(destinazione.name)
        vecchio = destinazione.read_text(encoding="utf-8") if destinazione.exists() else None
        if vecchio == contenuto:
            continue
        if argomenti.check:
            disallineate.append(destinazione.name)
        else:
            destinazione.write_text(contenuto, encoding="utf-8", newline="\n")
            print(f"scritto {destinazione.relative_to(RADICE).as_posix()}")

    for superflua in sorted(p for p in SITO.glob("sezione-*.qmd") if p.name not in attesi):
        if argomenti.check:
            disallineate.append(superflua.name)
        else:
            superflua.unlink()
            print(f"rimosso site/{superflua.name}")

    if argomenti.check:
        if disallineate:
            print(
                "le pagine delle sezioni non sono allineate al corpus: "
                + ", ".join(sorted(disallineate)),
                file=sys.stderr,
            )
            return 1
        print(f"site/: {len(attesi)} sezioni allineate al corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
