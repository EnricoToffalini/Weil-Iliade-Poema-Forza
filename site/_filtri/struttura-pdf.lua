--[[
  Differenze volute fra il sito e il libro in PDF.

  Sul web il saggio è diviso in dieci sezioni, una per pagina: dieci pagine da
  mille parole si leggono, una da diecimila no. La divisione però è redazionale,
  e nel libro non deve lasciare traccia: «L’Iliade ou le poème de la force» è un
  saggio continuo, senza capitoli e senza titoli interni.

  Il filtro fa quindi tre cose, e soltanto sul PDF:

  * toglie i titoli «§ N» delle sezioni. Nel libro Quarto li renderebbe con
    `\chapter`, che porta con sé un cambio di pagina: via il titolo, via il
    cambio di pagina, e il testo torna a scorrere;
  * scarta la pagina iniziale, che descrive il sito e non il testo;
  * lascia invece la «Nota al testo», che vale per entrambe le rese: comincia
    con un titolo suo e quindi, giustamente, su una pagina nuova.

  È dichiarato solo sotto `pdf` in `_quarto.yml`: le pagine HTML non lo vedono.
]]

local APERTURA = "L’Iliade, o il poema della forza"   -- titolo della pagina iniziale
local NOTA_AL_TESTO = "Nota al testo"

local function titolo(intestazione)
  return pandoc.utils.stringify(intestazione.content)
end

-- Un titolo di sezione: «§ 1», «§ 2», … Nient'altro nel libro ha questa forma.
local function e_marcatore_di_sezione(testo)
  return testo:match("^§%s*%d+$") ~= nil
end

function Pandoc(documento)
  local blocchi = pandoc.Blocks({})
  -- I capitoli confluiscono in un solo documento Pandoc: si attraversa una
  -- volta sola, tenendo conto di dove ci si trova.
  local dentro_apertura = false

  for _, blocco in ipairs(documento.blocks) do
    if blocco.t == "Header" and blocco.level == 1 then
      local testo = titolo(blocco)

      if testo == APERTURA then
        -- La pagina iniziale del sito non entra nel libro: si salta il titolo
        -- e tutto quello che segue, fino al capitolo successivo.
        dentro_apertura = true
        goto continua
      end

      dentro_apertura = false

      if e_marcatore_di_sezione(testo) then
        -- Via il titolo, e con esso il cambio di pagina: il saggio prosegue.
        goto continua
      end

      if testo == NOTA_AL_TESTO then
        -- Resta com'è: è un testo a sé e apre una pagina nuova.
        blocco.classes:insert("unnumbered")
      end
    end

    if not dentro_apertura then
      blocchi:insert(blocco)
    end

    ::continua::
  end

  documento.blocks = blocchi
  return documento
end
