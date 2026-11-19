-- Splits the line under each "### Job Title" ("**Company** — City, ST | Mon YYYY – Mon YYYY")
-- into <div class="role-meta"><span class="where">…</span><span class="when">…</span></div>
-- so print.css can right-align the dates. HTML/PDF build only; .docx is untouched.
function Pandoc(doc)
  local blocks = doc.blocks
  for i = 1, #blocks - 1 do
    local h, p = blocks[i], blocks[i + 1]
    if h.t == "Header" and h.level == 3 and p.t == "Para" then
      local where, when, seen = {}, {}, false
      for _, el in ipairs(p.content) do
        if not seen and el.t == "Str" and el.text == "|" then
          seen = true
        elseif seen then
          table.insert(when, el)
        else
          table.insert(where, el)
        end
      end
      if seen then
        while #where > 0 and where[#where].t == "Space" do table.remove(where) end
        while #when > 0 and when[1].t == "Space" do table.remove(when, 1) end
        blocks[i + 1] = pandoc.Div(
          { pandoc.Plain({ pandoc.Span(where, { class = "where" }), pandoc.Span(when, { class = "when" }) }) },
          { class = "role-meta" }
        )
      end
    end
  end
  return doc
end
