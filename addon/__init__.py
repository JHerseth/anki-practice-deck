"""Practice deck: practise a deck's cards without changing their schedule (see README.md).

Hook registration only. Everything with aqt is in ui.py; practice.py runs without it, so the
tests import it directly."""
from .log import log

try:
    from aqt import mw
except ImportError:                 # imported outside Anki
    mw = None

if mw is not None:
    try:
        from . import ui
        ui.setup()
    except Exception as e:          # never take Anki's startup down with us
        log("setup failed:", repr(e))
