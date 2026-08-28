# Immagini del progetto

`cover.jpg` — copertina del saggio: la piana di Troia, il carro vuoto e il
caduto con lo scudo. Corrisponde alla prima citazione omerica del testo, i
cavalli che «facevano risuonare i carri vuoti per le strade della guerra».

È usata in due punti, entrambi configurati in `site/_quarto.yml`:

- `book: image:` — alimenta le anteprime social (Open Graph, Twitter card). Il
  file compare anche fra le `resources:` del progetto: da sola la chiave
  `image` non basta a farlo pubblicare in `docs/`.
- il blocco `eso-pic` in coda a `format: pdf: include-in-header:` — la disegna a
  tutta pagina come sfondo della sola copertina del PDF, con il titolo
  sovrastampato.

L'immagine è 1024×1536, cioè 2:3, mentre la pagina A5 è 148:210. Nel PDF se ne
impone la larghezza e la si ancora in basso: riempie la pagina senza deformarsi,
e l'eccedenza viene tagliata in alto, dove c'è solo cielo.

Non c'è una favicon: non esiste un'immagine pensata per quel formato, e la
copertina ridotta a sedici pixel non si leggerebbe.

Nel testo non ci sono illustrazioni: il saggio è tutto prosa e citazioni
omeriche.
