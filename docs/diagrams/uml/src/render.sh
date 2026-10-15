#!/usr/bin/env bash
# Rend les .puml de ce dossier en PNG dans le dossier parent.
# Usage : PLANTUML_JAR=/chemin/plantuml.jar GRAPHVIZ_DOT=/chemin/dot ./render.sh [fichier.puml ...]
set -euo pipefail
cd "$(dirname "$0")"
files=("$@"); [ ${#files[@]} -eq 0 ] && files=(*.puml)
java -DPLANTUML_LIMIT_SIZE=16384 -jar "${PLANTUML_JAR:?définir PLANTUML_JAR}" -charset UTF-8 -tpng -o .. "${files[@]}"
