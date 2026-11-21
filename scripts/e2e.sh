#!/usr/bin/env bash
# Run the add-on in a throwaway Anki (flatpak, offscreen) on a new, empty collection, with the
# dev/e2e driver making a few decks and clicking through a practice session. Your own Anki folder
# and profiles are not touched: the base folder is $BASE, a separate single-instance key keeps it
# apart from a running Anki, and the test profile has no AnkiWeb login, so nothing syncs.
#   scripts/e2e.sh
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${BASE:-$HOME/.var/app/net.ankiweb.Anki/data/practice-deck-e2e}
out="$BASE/out"
mkdir -p "$BASE/addons21" "$out"
if [ ! -f "$BASE/prefs21.db" ]; then     # Anki's own ProfileManager, so Anki skips its first-run language picker
  flatpak run --filesystem="$BASE" --command=python3 net.ankiweb.Anki -c "
from pathlib import Path
from aqt.profiles import ProfileManager
pm = ProfileManager(Path('$BASE'))
pm.setupMeta()
pm.create('User 1')
pm.load('User 1')
pm.meta['firstRun'] = False
pm.meta['defaultLang'] = 'en_US'
pm.meta['check_for_updates'] = False
pm.save()"
fi
ADDONS="$BASE/addons21" scripts/dev-install.sh >/dev/null
mkdir -p "$BASE/addons21/practice_deck_e2e" "$BASE/User 1"
cp dev/e2e/practice_deck_e2e/__init__.py "$BASE/addons21/practice_deck_e2e/"
rm -f -- "$BASE/User 1/collection.anki2" "$BASE/User 1/collection.anki2-wal" "$BASE/User 1/collection.anki2-shm" "$out/results.json"
timeout 300 flatpak run --env=QT_QPA_PLATFORM=offscreen --env=ANKI_SINGLE_INSTANCE_KEY=practice-deck-e2e \
  --env=QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --env=PRACTICE_DECK_E2E_OUT="$out" \
  net.ankiweb.Anki -b "$BASE" >"$BASE/anki-e2e.log" 2>&1 || true
if [ -f "$out/results.json" ]; then
  python3 -c "import json,sys; r=json.load(open(sys.argv[1])); [print(('ok  ' if s['ok'] else 'FAIL'), s['step'], '' if s['ok'] else s['detail']) for s in r['steps']]; sys.exit(0 if r['ok'] else 1)" "$out/results.json"
else
  echo "no results; see $BASE/anki-e2e.log"; tail -30 "$BASE/anki-e2e.log"; exit 1
fi
