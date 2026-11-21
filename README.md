# Practice deck

An Anki desktop add-on: **Practice deck** in a deck's ⚙ menu (the deck list) practises the deck's
cards without changing their schedule.

## Using it

- **Practice deck** puts the deck's cards and its subdecks', shuffled, in a filtered deck
  ("Practice deck: 本 › 第3章") with rescheduling off, and starts the review. Suspended cards stay
  out; so do buried cards and cards already in another filtered deck (Anki never puts those in a
  filtered deck).
- **Again** and **Hard** show a card again after a while (1 and 10 minutes, the filtered deck's own
  preview delays, which its options change). **Good** and **Easy** send it back to its deck.
- **With every card passed** the practice deck is removed and Anki goes back to the deck list.
  A session finished on another device is removed after the next sync.
- **Left half way**, the practice deck stays, with the cards not yet passed. Practice deck on the
  same deck then asks: **Resume** (go on with those), **Start over** (every card again) or Cancel.
  Anki's own Delete on the practice deck ends the session: it sends the cards home and deletes none.
- A deck and its subdecks can each have a session; a card is in one at a time.
- Edit → Undo takes a new session back in one step ("Practice deck 本::第3章").

## What it changes, and what it doesn't

- A card's due date, interval, ease, review and lapse counts and FSRS memory state are the same
  after a session as before it, whatever was answered.
- The answers are written to the review log (as Anki does for any filtered deck), so they show in
  the statistics and in Review Heatmap. They are logged as filtered-deck reviews without an ease
  factor, which FSRS leaves out: a card's memory state computes the same with them as without.
- With FSRS on, Anki keeps its own notes in an answered card up to date: the preset's decay, and
  for a card without a memory state, the one its review history gives it anyway. Neither moves a
  due date.
- **While a session is unfinished its cards are in the practice deck, not in their own deck**: not
  in its counts and not in its reviews. Opening the profile names the unfinished sessions.
- The cards and the practice deck sync like any change. AnkiDroid and AnkiMobile show it as an
  ordinary filtered deck, and it can be reviewed there; the tidying up happens on the desktop.
- A card suspended or buried during a session stays in the practice deck until the session is
  started over or the practice deck deleted.

## Development

`addon/practice.py` finds, builds and removes the sessions and runs without Anki's GUI;
`addon/ui.py` is the menu entry, the question and the hooks. Nothing is saved: a practice deck is
told apart by its name, rescheduling and search (`did:<the deck>,<its subdecks>`).

```bash
python3 -m venv .venv && .venv/bin/pip install "anki>=26.9,<26.10"
.venv/bin/python -m unittest discover -s tests -t .      # the sessions, on a made-up collection
scripts/e2e.sh                                           # a session clicked through in a throwaway Anki (the flatpak, offscreen)
scripts/dev-install.sh                                   # copy into the flatpak Anki's addons21; restart Anki
```

`scripts/e2e.sh` uses its own base folder (`~/.var/app/net.ankiweb.Anki/data/practice-deck-e2e`),
never your Anki folder. Tested on Anki 26.09.
