"""A small collection with known cards, for the tests."""
import os
import tempfile
import time

from anki.collection import Collection
from anki.scheduler.v3 import CardAnswer

RATING = {1: CardAnswer.AGAIN, 2: CardAnswer.HARD, 3: CardAnswer.GOOD, 4: CardAnswer.EASY}


def make_col(path=None):
    """Deck "本" with two chapters, made 100 days ago (in a collection made today, today is day 0,
    and Anki reads a home due date of 0 as none):

      本              上手  learning, 10 minutes into its steps
      本::第1章       漢字  review, due in 20 days (ivl 30) · 読む  review, due today (ivl 3), with an FSRS memory state
                      書く  new · 話す  relearning (ivl 8, one lapse)
      本::第2章       近い  new, suspended · 遠い  new, buried · 高い  new
      Other           other  new, not in the deck"""
    path = path or os.path.join(tempfile.mkdtemp(), "collection.anki2")
    col = Collection(path)
    col.db.execute("update col set crt = crt - 86400 * 100")
    col.close()
    col = Collection(path)
    basic = col.models.by_name("Basic")
    ids = {}
    for term, deck in [("上手", "本"), ("漢字", "本::第1章"), ("読む", "本::第1章"), ("書く", "本::第1章"), ("話す", "本::第1章"),
                       ("近い", "本::第2章"), ("遠い", "本::第2章"), ("高い", "本::第2章"), ("other", "Other")]:
        n = col.new_note(basic)
        n["Front"], n["Back"] = term, "x"
        col.add_note(n, col.decks.id(deck))
        ids[term] = n.cards()[0].id
    today, now = col.sched.today, int(time.time())
    col.db.execute("update cards set type = 1, queue = 1, due = ?, left = 1001, reps = 1 where id = ?", now + 600, ids["上手"])
    col.db.execute("update cards set type = 2, queue = 2, ivl = 30, due = ?, factor = 2500, reps = 5 where id = ?", today + 20, ids["漢字"])
    col.db.execute("update cards set type = 2, queue = 2, ivl = 3, due = ?, factor = 2300, reps = 3, data = ? where id = ?",
                   today, '{"s":3.2,"d":5.1,"dr":0.9}', ids["読む"])
    col.db.execute("update cards set type = 3, queue = 1, ivl = 8, due = ?, factor = 2100, reps = 7, lapses = 1, left = 1001 where id = ?",
                   now + 300, ids["話す"])
    col.sched.suspend_cards([ids["近い"]])
    col.sched.bury_cards([ids["遠い"]])
    return col, ids


def cards(col):
    """Every card's row but for when it last changed (mod, usn), {card id: row}."""
    return {r[0]: tuple(r) for r in col.db.all(
        "select id, nid, did, ord, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data from cards")}


def answer_one(col, ease, n=0):
    """Answer the card Anki's reviewer would show now in the current deck. Its id, None when no card is offered."""
    queued = col.sched.get_queued_cards(fetch_limit=1)
    if not queued.cards:
        return None
    top = queued.cards[0]
    state = {1: top.states.again, 2: top.states.hard, 3: top.states.good, 4: top.states.easy}[ease]
    col.sched.answer_card(CardAnswer(card_id=top.card.id, current_state=top.states.current, new_state=state, rating=RATING[ease],
                                     answered_at_millis=int(time.time() * 1000) + n, milliseconds_taken=1000))
    return top.card.id


def answer(col, did, eases):
    """Review deck did, answering with eases in turn (the last one from then on) until no card is
    offered or 100 are answered. The card ids, in the order answered."""
    col.decks.select(did)
    done = []
    while len(done) < 100:
        cid = answer_one(col, eases[min(len(done), len(eases) - 1)], len(done))
        if cid is None:
            break
        done.append(cid)
    return done
