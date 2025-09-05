# En la carpeta del repo / proyecto
$prompt = Get-Content -Raw .\prompt.txt   # preserva saltos de línea
codex $prompt                             # modo interactivo
# Variantes útiles:
# codex -q $prompt                         # no interactivo (quiet)
# codex -a full-auto $prompt               # más autonomía
