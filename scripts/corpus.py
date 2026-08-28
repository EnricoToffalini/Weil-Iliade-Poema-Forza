"""Lettura del corpus: un solo saggio, in francese e in italiano.

Il corpus è la fonte autorevole. Questo modulo lo legge e lo scompone nei
blocchi che tutto il resto del progetto usa come unità minima: un paragrafo di
prosa, una citazione omerica in versi, il titolo, la nota di Simone Weil.

Gli identificatori dei blocchi (`h001`, `p001`, `v001`, `n001`) sono quelli già
presenti nella rappresentazione strutturata consegnata insieme al testo
francese. Sono stabili: legano il francese all'italiano, i punti di cesura
editoriale dichiarati in `site/sezioni.yml` e le pagine generate del sito. Non
vanno rinumerati.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CORPUS = RADICE / "corpus"
FR_MD = CORPUS / "fr" / "iliade-poeme-force.md"
FR_JSON = CORPUS / "fr" / "iliade-poeme-force.json"
IT_MD = CORPUS / "it" / "iliade-poema-forza.md"
MANIFEST = CORPUS / "manifest.yml"
SITO = RADICE / "site"
SEZIONI = SITO / "sezioni.yml"

# Marcatore di blocco nel corpus italiano:  <!-- @p001 prose -->
MARCATORE = re.compile(r"^<!--\s*@(?P<id>[hpvn]\d{3})\s+(?P<tipo>[a-z]+)\s*-->$")

# Il segnaposto della traduzione ancora da fare. Deve restare riconoscibile a
# colpo d'occhio: `validate_corpus.py` conta su questa forma per garantire che
# nessun testo provvisorio possa essere scambiato per traduzione definitiva.
SEGNAPOSTO = "[TRADUZIONE ITALIANA"

TIPI = ("heading", "prose", "verse", "note")
# Il titolo del saggio non è materia di traduzione: è fissato dal progetto.
# Il conteggio dello stato dell'opera riguarda quindi solo gli altri blocchi.
TIPI_DA_TRADURRE = ("prose", "verse", "note")
PREFISSI = {"heading": "h", "prose": "p", "verse": "v", "note": "n"}


class ErroreDiCorpus(RuntimeError):
    """Corpus, rappresentazione strutturata e configurazione non coincidono."""


@dataclass(frozen=True)
class Blocco:
    """Un'unità di testo: titolo, prosa, versi o nota."""

    id: str
    tipo: str
    righe: tuple[str, ...]
    etichetta: str | None = None  # solo per le note: l'etichetta di `[^1]`

    @property
    def parole(self) -> int:
        return sum(len(riga.split()) for riga in self.righe)

    @property
    def e_segnaposto(self) -> bool:
        return any(SEGNAPOSTO in riga for riga in self.righe)


# ---------------------------------------------------------------------------
# lettura


def dividi_front_matter(testo: str) -> tuple[str, str]:
    """Separa il front matter YAML dal corpo, senza interpretarlo."""
    if not testo.startswith("---\n"):
        return "", testo
    fine = testo.find("\n---\n", 3)
    if fine < 0:
        raise ErroreDiCorpus("front matter aperto e mai chiuso")
    return testo[4:fine + 1], testo[fine + 5:]


def _paragrafi(corpo: str) -> list[str]:
    return [p.strip("\n") for p in re.split(r"\n[ \t]*\n", corpo) if p.strip()]


def _righe_di_versi(paragrafo: str) -> list[str]:
    """Toglie il segno di citazione e gli a-capo forzati, tenendo i versi."""
    return [re.sub(r"^>\s?", "", riga.strip()).rstrip() for riga in paragrafo.split("\n")]


def leggi_francese_markdown(percorso: Path = FR_MD) -> list[Blocco]:
    """Scompone il Markdown francese, fonte testuale primaria del progetto.

    Il francese non porta marcatori: i blocchi si riconoscono dalla forma
    (`#` titolo, `>` citazione in versi, `[^n]:` nota) e ricevono il proprio
    identificatore dall'ordine, che è quello della rappresentazione
    strutturata. `leggi_francese()` verifica che le due letture coincidano.
    """
    _, corpo = dividi_front_matter(percorso.read_text(encoding="utf-8"))
    blocchi: list[Blocco] = []
    contatori = dict.fromkeys(TIPI, 0)

    for paragrafo in _paragrafi(corpo):
        prima = paragrafo.lstrip()
        if prima.startswith("#"):
            tipo, righe, etichetta = "heading", [prima.lstrip("# ").strip()], None
        elif prima.startswith(">"):
            tipo, righe, etichetta = "verse", _righe_di_versi(paragrafo), None
        elif prima.startswith("[^"):
            trovato = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", paragrafo, re.S)
            if not trovato:
                raise ErroreDiCorpus(f"nota malformata: {paragrafo[:60]!r}")
            tipo = "note"
            righe = [trovato.group(2).strip()]
            etichetta = trovato.group(1)
        else:
            tipo, righe, etichetta = "prose", [paragrafo.strip()], None
        contatori[tipo] += 1
        blocchi.append(
            Blocco(f"{PREFISSI[tipo]}{contatori[tipo]:03d}", tipo, tuple(righe), etichetta)
        )
    return blocchi


def leggi_francese_json(percorso: Path = FR_JSON) -> tuple[dict, list[Blocco]]:
    """Legge la rappresentazione strutturata: serve solo da riscontro."""
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    blocchi = []
    for voce in dati["blocks"]:
        tipo = voce["type"]
        righe = tuple(voce["lines"]) if tipo == "verse" else (voce["text"],)
        blocchi.append(Blocco(voce["id"], tipo, righe, voce.get("label")))
    return dati.get("metadata", {}), blocchi


def leggi_francese() -> list[Blocco]:
    """Il testo francese, letto dal Markdown e riscontrato sul JSON.

    Il Markdown è la fonte: se le due rappresentazioni divergono l'errore va
    risolto, non aggirato. Il JSON non introduce mai modifiche al testo.
    """
    dal_markdown = leggi_francese_markdown()
    _, dal_json = leggi_francese_json()
    if len(dal_markdown) != len(dal_json):
        raise ErroreDiCorpus(
            f"il Markdown francese ha {len(dal_markdown)} blocchi, "
            f"la rappresentazione strutturata {len(dal_json)}"
        )
    for md, js in zip(dal_markdown, dal_json):
        if (md.id, md.tipo, md.righe) != (js.id, js.tipo, js.righe):
            raise ErroreDiCorpus(
                f"il blocco {md.id} differisce fra Markdown e JSON strutturato"
            )
    return dal_markdown


def leggi_italiano(percorso: Path = IT_MD) -> list[Blocco]:
    """Scompone il corpus italiano, che porta i marcatori `<!-- @id tipo -->`.

    I marcatori tengono agganciata la traduzione al francese un blocco per
    volta: riempire un segnaposto non può spostare le cesure editoriali né gli
    URL delle pagine.

    Il blocco va dal proprio marcatore fino al marcatore successivo: fra il
    marcatore e il testo può esserci una riga vuota, come pure fra un blocco e
    l'altro. Le righe vuote in testa e in coda al contenuto non contano.
    """
    if not percorso.exists():
        raise ErroreDiCorpus(f"manca {percorso.relative_to(RADICE).as_posix()}")
    _, corpo = dividi_front_matter(percorso.read_text(encoding="utf-8"))
    blocchi: list[Blocco] = []

    corrente: tuple[str, str] | None = None
    contenuto: list[str] = []

    def chiudi() -> None:
        if corrente is None:
            return
        identificatore, tipo = corrente
        righe = list(contenuto)
        while righe and not righe[0].strip():
            righe.pop(0)
        while righe and not righe[-1].strip():
            righe.pop()

        etichetta = None
        if tipo == "heading":
            testo = [righe[0].lstrip("# ").strip()] if righe else []
        elif tipo == "verse":
            testo = [r for r in _righe_di_versi("\n".join(righe)) if r.strip()]
        elif tipo == "note":
            nota = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", "\n".join(righe).strip(), re.S)
            if not nota:
                raise ErroreDiCorpus(f"{identificatore}: nota malformata")
            etichetta, testo = nota.group(1), [nota.group(2).strip()]
        else:
            testo = ["\n".join(righe).strip()]

        if not any(r.strip() for r in testo):
            raise ErroreDiCorpus(f"{identificatore}: blocco senza contenuto")
        blocchi.append(Blocco(identificatore, tipo, tuple(testo), etichetta))

    for riga in corpo.split("\n"):
        trovato = MARCATORE.match(riga.strip())
        if trovato:
            chiudi()
            tipo = trovato.group("tipo")
            if tipo not in TIPI:
                raise ErroreDiCorpus(
                    f"{trovato.group('id')}: tipo sconosciuto {tipo!r}"
                )
            corrente = (trovato.group("id"), tipo)
            contenuto = []
        elif corrente is None:
            if riga.strip():
                raise ErroreDiCorpus(
                    "ogni blocco del corpus italiano deve cominciare con il proprio "
                    f"marcatore `<!-- @id tipo -->`; trovato invece {riga.strip()[:60]!r}"
                )
        else:
            contenuto.append(riga)
    chiudi()
    return blocchi


# ---------------------------------------------------------------------------
# sezioni editoriali


def leggi_sezioni(percorso: Path = SEZIONI) -> list[dict]:
    """I punti di cesura editoriali dichiarati in `site/sezioni.yml`.

    Una voce per sezione, con `numero`, `inizio` (identificatore del primo
    blocco) e `pagina` (nome del file generato, senza estensione).
    """
    import yaml

    dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    inizi = dati.get("inizi_sezione") or []
    if not inizi:
        raise ErroreDiCorpus(f"{percorso.name}: nessun punto di cesura dichiarato")
    return [
        {"numero": numero, "inizio": inizio, "pagina": f"sezione-{numero}"}
        for numero, inizio in enumerate(inizi, 1)
    ]


def dividi_in_sezioni(blocchi: list[Blocco], sezioni: list[dict]) -> list[list[Blocco]]:
    """Taglia la sequenza dei blocchi ai punti dichiarati.

    Le cesure cadono sempre fra un blocco e l'altro: nessuna citazione omerica
    può quindi essere spezzata a metà. Ogni sezione deve inoltre cominciare con
    un blocco di prosa, perché i versi seguono sempre la prosa che li
    introduce; il controllo è in `validate_corpus.py`.
    """
    posizioni = {blocco.id: indice for indice, blocco in enumerate(blocchi)}
    limiti = []
    for sezione in sezioni:
        if sezione["inizio"] not in posizioni:
            raise ErroreDiCorpus(
                f"sezione {sezione['numero']}: il blocco {sezione['inizio']} non esiste"
            )
        limiti.append(posizioni[sezione["inizio"]])
    if limiti != sorted(limiti) or len(set(limiti)) != len(limiti):
        raise ErroreDiCorpus("i punti di cesura non sono in ordine crescente")
    # La prima sezione parte dall'inizio del testo: il titolo del saggio le
    # appartiene, anche se non è il blocco dichiarato come suo inizio.
    limiti[0] = 0
    estremi = limiti + [len(blocchi)]
    return [blocchi[inizio:fine] for inizio, fine in zip(estremi, estremi[1:])]


# ---------------------------------------------------------------------------
# utilità


def impronta(percorso: Path) -> str:
    """SHA-256 del file, calcolato sui byte così come stanno su disco."""
    return hashlib.sha256(percorso.read_bytes()).hexdigest()
