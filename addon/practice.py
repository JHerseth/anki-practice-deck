"""Practice decks: a deck's cards in a filtered deck that leaves their schedule alone.
Collection-level functions that ui.py runs inside a CollectionOp; no aqt here.

A practice deck is a filtered deck ("Practice deck: 本 › 第3章") with rescheduling off (Anki's preview
mode) and one search, did:<the deck>,<its subdecks>: every card of the deck and the decks under it
that a filtered deck can take, shuffled. Anki leaves out suspended and buried cards and those
already in a filtered deck. Again and Hard show a card again after a while (the deck's preview
delays, Anki's own: 1 and 10 minutes), Good and Easy send it home as it was: its due date,
interval, ease, counts and FSRS memory state are untouched. The answers are still written to the
review log, as filtered-deck entries without an ease factor, the ones FSRS leaves out. With FSRS
on, Anki also keeps its own notes in an answered card up to date: the preset's decay, and for a
card that has no memory state yet, the one its history gives it. Neither moves a due date.

So the cards still in a practice deck are the ones not yet passed, and a session can be taken up
again later. Until then they are away from their own deck: not in its counts, not in its reviews.

Nothing is saved about a session. A practice deck is told apart by its name, rescheduling and
search, and the search's first deck is the one it practises, so a renamed deck keeps its session and
a session made on another device is found after a sync. A deck has one session: starting again
rebuilds its practice deck, and a second one (two devices that each made one before syncing) is
removed then, which sends its cards home."""
import re

NAME = "Practice deck: {}"
TERM = re.compile(r"did:(\d+)(?:,\d+)*")


def sessions(col, source=0):
    """The practice decks, {its id: the id of the deck it practises}; only source's when given."""
    found = {}
    for d in col.decks.all_names_and_ids(include_filtered=True):
        if not d.name.startswith(NAME.format("")):
            continue
        deck = col.decks.get(d.id, default=False)
        terms = (deck.get("terms") or []) if deck else []
        of = TERM.fullmatch(str(terms[0][0])) if len(terms) == 1 else None
        if of and deck["dyn"] and not deck.get("resched") and source in (0, int(of[1])):
            found[d.id] = int(of[1])
    return found


def left(col, did):
    """How many cards are still in a practice deck: the ones not yet passed."""
    return col.db.scalar("select count() from cards where did = ?", did)


def unfinished(col, source=0):
    """The practice decks with cards left, {its id: how many}; only source's when given."""
    counts = {d: left(col, d) for d in sessions(col, source)}
    return {d: n for d, n in counts.items() if n}


def finished(col):
    """The practice decks with no cards left, {its id: the id of the deck it practised}: answered
    through, here or on another device, or emptied by hand."""
    return {d: source for d, source in sessions(col).items() if not left(col, d)}


def _search(col, source):
    """The deck's cards and its subdecks', by deck id: the deck's own first (sessions)."""
    return "did:" + ",".join(map(str, [source] + [d for d in col.decks.deck_and_child_ids(source) if d != source]))


def _free(col, search, ours):
    """Of the cards a search finds, the ones a practice deck can take: Anki leaves out suspended and
    buried cards and those in a filtered deck (this deck's own practice decks are emptied first,
    so theirs count). Building a deck that takes none fails, and a failed change clears Anki's
    undo history."""
    home = f"(-deck:filtered OR did:{','.join(map(str, ours))})" if ours else "-deck:filtered"
    return col.find_cards(f"({search}) -is:suspended -is:buried {home}")


def start(col, source):
    """Practise a deck from scratch: its practice deck built, or rebuilt, on the cards it can take
    (_free), shuffled, in preview mode. One undo entry, "Practice deck 本::第3章". The practice deck's id,
    with the changes."""
    from anki.collection import OpChangesWithId
    from anki.decks import FilteredDeckConfig
    name = col.decks.name(source)
    ours = list(sessions(col, source))
    search = _search(col, source)
    ids = _free(col, search, ours)
    if not ids:
        raise ValueError(f"No cards to practise in {name}: they are all suspended, buried or in another filtered deck.")
    term = FilteredDeckConfig.SearchTerm
    pos = col.add_custom_undo_entry(f"Practice deck {name}")
    keep, *others = ours or [0]
    if others:
        col.decks.remove(others)
    deck = col.sched.get_or_create_filtered_deck(keep)
    deck.name = NAME.format(name.replace("::", " › "))      # "::" would make it a subdeck
    del deck.config.search_terms[:]
    deck.config.search_terms.append(term(search=search, limit=len(ids), order=term.RANDOM))
    deck.config.reschedule = False
    did = col.sched.add_or_update_filtered_deck(deck).id
    return OpChangesWithId(changes=col.merge_undo_entries(pos), id=did)


def clean_up(col):
    """Remove the practice decks with no cards left (finished). Anki's own undo entry, "Delete Deck"."""
    return col.decks.remove(list(finished(col)))
