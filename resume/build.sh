#!/bin/sh
# Export each variant .md to YYYY-MM/ as .docx (pandoc + reference.docx styles) and .pdf (pandoc HTML + print.css via headless Chrome).
# Also exports tailored/YYYY-MM/*.md (per-posting copies) next to their sources.
# Usage: sh build.sh [YYYY-MM] [tailored]   (month defaults to current; "tailored" skips the four variants)
set -eu
cd "$(dirname "$0")"
month="${1:-$(date +%Y-%m)}"
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p "$month"
export_md() {
  pandoc "$1" -f gfm -o "$2.docx" --reference-doc=reference.docx
  pandoc "$1" -f gfm -s --embed-resources --css=print.css --lua-filter=role-meta.lua -V pagetitle="Roosevelt Segura" -o "$2.html"
  "$chrome" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$PWD/$2.pdf" "file://$PWD/$2.html" 2>/dev/null
  rm "$2.html"
  echo "built: $2.docx $2.pdf"
}
if [ "${2:-}" != tailored ]; then
  for v in it-support-tech service-desk systems-infra devops-cloud; do
    src="$v/resume-$month-$v.md"
    [ -f "$src" ] || { echo "skip: $src missing"; continue; }
    export_md "$src" "$month/resume-$month-$v"
  done
fi
for src in tailored/"$month"/*.md; do
  [ -f "$src" ] || continue
  export_md "$src" "${src%.md}"
done
