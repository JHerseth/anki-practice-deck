#!/usr/bin/env bash
# Copy the add-on into Anki's add-ons folder (a copy: the flatpak can't follow a symlink into
# ~/Documents). Restart Anki afterwards. ADDONS overrides the folder.
#   scripts/dev-install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ADDONS=${ADDONS:-$HOME/.var/app/net.ankiweb.Anki/data/Anki2/addons21}
dest="$ADDONS/practice_deck"
mkdir -p "$dest"
cp addon/*.py addon/manifest.json "$dest/"
echo "installed in $dest; restart Anki"
