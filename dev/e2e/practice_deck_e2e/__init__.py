"""End-to-end check of Practice deck inside a real, throwaway Anki (run by scripts/e2e.sh, never
in your own Anki folder). On a new collection it makes a small deck tree and goes through a
session the way a person would: the deck list's ⚙ menu, a few answers, leaving half way, Resume,
Cancel, Start over, answering it through (the practice deck removed, back at the deck list), a
deck with nothing to practise, a session finished on another device, and the note about
unfinished sessions. Results go to $PRACTICE_DECK_E2E_OUT/results.json; then Anki quits."""
import json
import os
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QMenu, QTimer

OUT = os.environ.get("PRACTICE_DECK_E2E_OUT", "")
results = {"ok": True, "steps": []}
ids = {}

ui = practice = None    # the add-on's own modules, once it has loaded (scenario)


def check(step, ok, detail=""):
    results["steps"].append({"step": step, "ok": bool(ok), "detail": str(detail)})
    if not ok:
        results["ok"] = False


def make_decks():
    """本::第1章 (3 cards, one a review due in 20 days) · 本::第2章 (2 cards, one suspended) · Shut (1, suspended)"""
    col = mw.col
    basic = col.models.by_name("Basic")
    for term, deck in [("漢字", "本::第1章"), ("読む", "本::第1章"), ("書く", "本::第1章"), ("近い", "本::第2章"), ("遠い", "本::第2章"), ("shut", "Shut")]:
        n = col.new_note(basic)
        n["Front"], n["Back"] = term, "x"
        col.add_note(n, col.decks.id(deck))
        ids[term] = n.cards()[0].id
    col.db.execute("update cards set type = 2, queue = 2, ivl = 30, due = ?, factor = 2500, reps = 5 where id = ?", col.sched.today + 20, ids["漢字"])
    col.sched.suspend_cards([ids["遠い"], ids["shut"]])
    mw.reset()


def cards():
    """Every card's row but for when it last changed."""
    return [tuple(r) for r in mw.col.db.all(
        "select id, did, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, data from cards order by id")]


def session(source):
    """(the deck's practice deck, the cards in it): (0, 0) without one."""
    decks = list(practice.sessions(mw.col, source))
    return (decks[0], practice.left(mw.col, decks[0])) if decks else (0, 0)


def menu_action(did):
    """Practice deck in the ⚙ menu Anki's deck list opens for a deck, and the menu; (None, menu) when it isn't there."""
    before = set(mw.findChildren(QMenu))
    mw.deckBrowser._showOptions(str(did))
    menu = next(m for m in mw.findChildren(QMenu) if m not in before)
    return next((a for a in menu.actions() if a.text() == "Practice deck"), None), menu


def choose(did):
    action, menu = menu_action(did)
    action.trigger()
    menu.close()


def button(text):
    return next(b for b in ui._box.buttons() if b.text().replace("&", "") == text)


def answer(ease):
    yield 600
    mw.reviewer._showAnswer()
    yield 300
    mw.reviewer._answerCard(ease)
    yield 700


def tip():
    import aqt.utils
    label = aqt.utils._tooltipLabel
    return label.text() if label else ""


def scenario():
    global ui, practice
    import practice_deck.practice as practice
    import practice_deck.ui as ui
    make_decks()
    yield 1500
    book, ch1, shut = (mw.col.decks.id_for_name(n) for n in ("本", "本::第1章", "Shut"))
    home = cards()

    # the ⚙ menu, and a first session
    action, menu = menu_action(book)
    check("the deck's ⚙ menu has Practice deck", action is not None, [a.text() for a in menu.actions()])
    menu.close()
    choose(book)
    yield 2500
    did, left = session(book)
    check("Practice deck reviews the deck's cards in a practice deck, less the suspended one",
          mw.state == "review" and did and mw.col.decks.selected() == did and left == 4 and not mw.col.decks.get(did)["resched"],
          (mw.state, did, left))
    action, menu = menu_action(did)
    check("a filtered deck's menu has no Practice deck", action is None)
    menu.close()

    # two answers, away, and back: Resume
    yield from answer(3)
    yield from answer(4)
    check("Good and Easy send their cards home", session(book) == (did, 2), session(book))
    mw.moveToState("deckBrowser")
    yield 1500
    check("leaving half way keeps the session", session(book) == (did, 2) and mw.state == "deckBrowser", (session(book), mw.state))
    choose(book)
    yield 1000
    check("with cards left it asks", ui._box is not None and "2 cards left" in ui._box.text() and mw.state == "deckBrowser",
          ui._box and ui._box.text())
    button("Resume").click()
    yield 2500
    check("Resume reviews what is left", mw.state == "review" and mw.col.decks.selected() == did and session(book) == (did, 2)
          and ui._box is None, (mw.state, session(book)))

    # Cancel, then Start over
    mw.moveToState("deckBrowser")
    yield 1000
    choose(book)
    yield 1000
    button("Cancel").click()
    yield 1500
    check("Cancel changes nothing", mw.state == "deckBrowser" and session(book) == (did, 2) and ui._box is None, (mw.state, session(book)))
    choose(book)
    yield 1000
    button("Start over").click()
    yield 2500
    check("Start over rebuilds the practice deck with every card", mw.state == "review" and session(book) == (did, 4)
          and mw.col.decks.selected() == did, (mw.state, session(book)))

    # a subdeck's own session beside it: nothing left for it to take, so a tooltip
    mw.moveToState("deckBrowser")
    yield 1000
    choose(ch1)
    yield 2000
    check("a deck with nothing to practise says so", "No cards to practise in 本::第1章" in tip() and session(ch1) == (0, 0)
          and mw.state == "deckBrowser", (tip(), session(ch1), mw.state))
    choose(shut)
    yield 2000
    check("and so does a deck of suspended cards", "No cards to practise in Shut" in tip() and session(shut) == (0, 0), (tip(), session(shut)))

    # answer it through: Again and Hard keep a card, then everything passes
    choose(book)
    yield 1000
    button("Resume").click()
    yield 2500
    yield from answer(1)
    yield from answer(2)
    check("Again and Hard keep their cards", session(book) == (did, 4), session(book))
    for _ in range(4):
        yield from answer(3)
    yield 800                # its tooltip is up for three seconds
    check("the last card passed: the practice deck is gone and Anki is at the deck list",
          session(book) == (0, 0) and not mw.col.decks.name_if_exists(did) and mw.state == "deckBrowser"
          and QApplication.activeModalWidget() is None, (session(book), mw.state, QApplication.activeModalWidget()))
    check("it says so", "Practice finished: 本" in tip(), tip())
    check("every card is as it was", cards() == home, [(a, b) for a, b in zip(home, cards()) if a != b])
    logged = mw.col.db.all("select type, factor from revlog")
    check("the answers are logged as filtered-deck reviews without an ease factor", len(logged) == 8 and {tuple(r) for r in logged} == {(3, 0)}, logged)

    # an ordinary review ending leaves other sessions alone
    choose(ch1)
    yield 2500
    did, left = session(ch1)
    check("a subdeck has its own session", mw.state == "review" and left == 3 and mw.col.decks.name(did) == "Practice deck: 本 › 第1章",
          (mw.state, left, mw.col.decks.name_if_exists(did)))
    mw.moveToState("deckBrowser")
    yield 1500
    ui._profile_opened()
    check("opening the profile names the unfinished session", "Unfinished practice: 本::第1章 (3 cards)" in tip(), tip())

    # finished on another device: the practice deck comes back from the sync empty
    mw.col.sched.empty_filtered_deck(did)
    ui._profile_closing()
    gui_hooks.sync_did_finish()
    yield 1500
    check("the sync as the profile closes removes nothing", session(ch1) == (did, 0), session(ch1))
    ui._closing = False
    gui_hooks.sync_did_finish()
    yield 1500
    check("a sync removes a session finished elsewhere", session(ch1) == (0, 0) and not mw.col.decks.name_if_exists(did), session(ch1))
    check("and the cards are still as they were", cards() == home)

    # Edit → Undo on a new session
    choose(ch1)
    yield 2500
    check("a new session is one undo step", mw.col.undo_status().undo == "Practice deck 本::第1章", mw.col.undo_status().undo)


def run():
    steps = scenario()

    def advance():
        try:
            delay = next(steps)
        except StopIteration:
            return finish()
        except Exception:
            check("scenario", False, traceback.format_exc())
            return finish()
        QTimer.singleShot(delay, advance)
    QTimer.singleShot(2000, advance)


def finish():
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    QTimer.singleShot(500, mw.unloadProfileAndExit)


if OUT:
    gui_hooks.profile_did_open.append(run)
