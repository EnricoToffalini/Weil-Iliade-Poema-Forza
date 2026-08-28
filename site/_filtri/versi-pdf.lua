--[[
  Le citazioni omeriche nel PDF: `verse` invece di `quote`.

  Nel corpus le citazioni sono blocchi di citazione con un a-capo forzato per
  verso. Pandoc li rende in LaTeX come `quote`, che tratta il testo come prosa:
  un verso troppo lungo per la giustezza A5 va a capo allineato al margine
  della citazione, e a quel punto è indistinguibile dal verso successivo.

  L'ambiente `verse`, che LaTeX ha già, fa esattamente ciò che serve: rientra le
  sole righe di ricaduta, così che un verso spezzato dalla giustezza si
  riconosca a colpo d'occhio come continuazione. È importante qui più che
  altrove, perché Simone Weil dichiara nella sua unica nota di aver riprodotto
  scrupolosamente rigetti ed enjambement: gli a-capo sono parte di ciò che il
  saggio vuole mostrare.

  Il filtro tocca solo le citazioni in versi — quelle che contengono un a-capo
  forzato. Una citazione in prosa, se un giorno ce ne fosse una, resta `quote`.
]]

local function contiene_a_capo(blocchi)
  local trovato = false
  for _, blocco in ipairs(blocchi) do
    pandoc.walk_block(blocco, {
      LineBreak = function()
        trovato = true
      end,
    })
    if trovato then
      return true
    end
  end
  return false
end

function BlockQuote(citazione)
  if not FORMAT:match("latex") then
    return nil
  end
  if not contiene_a_capo(citazione.content) then
    return nil
  end

  local blocchi = pandoc.Blocks({ pandoc.RawBlock("latex", "\\begin{verse}") })
  for _, blocco in ipairs(citazione.content) do
    blocchi:insert(blocco)
  end
  blocchi:insert(pandoc.RawBlock("latex", "\\end{verse}"))
  return blocchi
end
