"""The Anki side, kept thin: sessions are found, built and removed by practice.py.

- "Practice deck" in the deck list's ⚙ menu, on every deck but a filtered one: the deck's session
  started (practice.start) and Anki's review opened on it. When the deck has a session with cards
  left it asks first: Resume it, or Start over;
- leaving the review with every card passed removes the practice deck and goes back to the deck
  list. A sync does the same without a word, for a session finished on another device (not the
  sync as the profile closes: the collection closes behind it);
- opening the profile names the unfinished sessions: their cards are away from their own decks;
- every hook body catches its own errors: Anki removes a hook that raises."""
from aqt import gui_hooks, mw
from aqt.errors import show_exception
from aqt.operations import CollectionOp
from aqt.operations.deck import set_current_deck
from aqt.qt import QMessageBox, Qt, qconnect
from aqt.utils import tooltip

from . import practice
from .log import log

_box = None         # the Resume or Start over question, while it is open
_closing = False    # between profile_will_close and the next profile_did_open


def _cards(n):
    return "1 card" if n == 1 else f"{n} cards"


def _review(deck_id):
    set_current_deck(parent=mw, deck_id=deck_id).success(lambda _: mw.moveToState("review")).run_in_background()


def _start(source):
    """The deck's session from scratch, then its review; a tooltip when it has no cards to practise."""
    def failed(e):
        if isinstance(e, ValueError):
            tooltip(str(e), period=6000)
        else:
            show_exception(parent=mw, exception=e)
    CollectionOp(parent=mw, op=lambda col: practice.start(col, source)).success(lambda out: _review(out.id)).failure(failed).run_in_background()


def _ask(name, count, resume, start_over):
    """Resume, Start over or Cancel, for a deck whose session has cards left. Not blocking: the
    answer calls resume() or start_over()."""
    global _box
    _box = box = QMessageBox(mw)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Practice deck")
    box.setText(f"{name} has a practice session with {_cards(count)} left.")
    box.setInformativeText("Resume it, or start over with all of the deck's cards?")
    again = box.addButton("Resume", QMessageBox.ButtonRole.AcceptRole)
    fresh = box.addButton("Start over", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(again)

    def answered(_result):
        global _box
        _box = None
        clicked = box.clickedButton()
        if clicked == again:
            resume()
        elif clicked == fresh:
            start_over()
    qconnect(box.finished, answered)
    box.open()


def practise(source):
    """Practice deck on a deck: its session started, or, when it has one with cards left, taken up
    again or started from scratch as the user says."""
    waiting = practice.unfinished(mw.col, source)
    if not waiting:
        return _start(source)
    did, count = next(iter(waiting.items()))
    _ask(mw.col.decks.name(source), count, lambda: _review(did), lambda: _start(source))


def _tidy(say):
    """Remove the finished practice decks; from the overview of one, back to the deck list (Anki asks
    to select a deck when the overview's is gone). say: a tooltip naming the decks practised."""
    col = mw.col
    done = practice.finished(col)
    if not done:
        return
    names = [n for n in map(col.decks.name_if_exists, done.values()) if n]
    here = col.decks.selected() in done

    def removed(_):
        if here and mw.state == "overview":
            mw.moveToState("deckBrowser")
        if say:
            tooltip("Practice finished" + (": " + ", ".join(names) if names else ""))
        log("removed", len(done), "finished practice deck(s)")
    CollectionOp(parent=mw, op=practice.clean_up).success(removed).run_in_background()


def _state_changed(new_state, old_state):
    try:
        if old_state == "review" and mw.col:
            _tidy(say=True)
    except Exception as e:
        log("leaving the review:", repr(e))


def _synced():
    try:
        if not _closing and mw.col:
            _tidy(say=False)
    except Exception as e:
        log("after the sync:", repr(e))


def _profile_opened():
    """Name the sessions with cards left: until they are finished or their practice decks deleted,
    those cards are not in their own decks' reviews."""
    global _closing
    _closing = False
    try:
        col = mw.col
        waiting = practice.unfinished(col)
        if waiting:
            sources = practice.sessions(col)
            tooltip("Unfinished practice: " + ", ".join(
                f"{col.decks.name_if_exists(sources[d]) or col.decks.name(d)} ({_cards(n)})" for d, n in waiting.items()), period=6000)
    except Exception as e:
        log("profile opened:", repr(e))


def _profile_closing():
    global _closing
    _closing = True


def _deck_menu(menu, deck_id):
    try:
        if mw.col.decks.is_filtered(deck_id):
            return
        action = menu.addAction("Practice deck")
        qconnect(action.triggered, lambda *_: practise(deck_id))
    except Exception as e:
        log("deck menu:", repr(e))


def setup():
    gui_hooks.deck_browser_will_show_options_menu.append(_deck_menu)
    gui_hooks.state_did_change.append(_state_changed)
    gui_hooks.sync_did_finish.append(_synced)
    gui_hooks.profile_did_open.append(_profile_opened)
    gui_hooks.profile_will_close.append(_profile_closing)
