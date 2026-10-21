-- Runs after citeproc: in a French paper, the descriptive labels of the reference list
-- (taken from the bibliography's howpublished and type fields) are given in French.
local fr = {
  ['News report'] = 'Article de presse',
  ['Web page'] = 'Page web',
  ['Web site'] = 'Site web',
  ['Official list'] = 'Liste officielle',
  ['Decree'] = 'Décret',
  ['Government bulletin'] = 'Bulletin du Gouvernement',
  ['Project reference page'] = 'Page de présentation du projet',
  ['Travel advice page'] = 'Conseils aux voyageurs',
  ['Legal summary'] = 'Synthèse juridique',
  ['White paper'] = 'Livre blanc',
  ['Addressing sheet'] = "Fiche d'adressage",
  ['UPU standard'] = "Norme de l'UPU",
  ['Dataset and repository'] = 'Jeu de données et dépôt',
  ['Dataset'] = 'Jeu de données',
  ['Software repository'] = 'Dépôt logiciel',
  ['Source code and data repository'] = 'Dépôt du code source et des données',
  ['Geofabrik extract'] = 'Extrait Geofabrik',
  ['arXiv preprint'] = 'Prépublication arXiv',
  ['Newsletter'] = "Lettre d'information",
  ['on the geodetic reference'] = 'sur la référence géodésique',
}

local function words(s)
  local t = {}
  for w in s:gmatch('%S+') do t[#t + 1] = w end
  return t
end

local phrases = {}
for k, v in pairs(fr) do phrases[#phrases + 1] = {words(k), v} end
table.sort(phrases, function(a, b) return #a[1] > #b[1] end)

-- Replace each phrase found as consecutive Str/Space inlines; the last word may carry punctuation.
local function translate(inls)
  local out = pandoc.Inlines{}
  local i = 1
  while i <= #inls do
    local done = false
    for _, p in ipairs(phrases) do
      local ws, j, ok, tail = p[1], i, true, ''
      for n, w in ipairs(ws) do
        local el = inls[j]
        if not el or el.t ~= 'Str' then ok = false break end
        if n == #ws then
          if el.text:sub(1, #w) ~= w then ok = false break end
          tail = el.text:sub(#w + 1)
          if tail:match('%w') then ok = false break end
        elseif el.text ~= w then ok = false break end
        j = j + 1
        if n < #ws then
          if not inls[j] or inls[j].t ~= 'Space' then ok = false break end
          j = j + 1
        end
      end
      if ok then
        out:insert(pandoc.Str(p[2] .. tail))
        i = j
        done = true
        break
      end
    end
    if not done then out:insert(inls[i]); i = i + 1 end
  end
  return out
end

function Pandoc(doc)
  local lang = pandoc.utils.stringify(doc.meta.lang or '')
  if not lang:match('^fr') then return nil end
  doc.blocks = doc.blocks:walk({
    Div = function(d)
      if d.identifier ~= 'refs' then return nil end
      return d:walk({Inlines = translate})
    end
  })
  return doc
end
