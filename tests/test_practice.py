import json
import time
import unittest

from addon import practice
from tests.helpers import answer, answer_one, cards, make_col

from anki.decks import FilteredDeckConfig       # after anki.collection (helpers): anki's imports are circular

FREE = ("上手", "漢字", "読む", "書く", "話す", "高い")     # the deck's cards a practice deck can take


class Practice(unittest.TestCase):
    def setUp(self):
        self.col, self.ids = make_col()
        self.book = self.col.decks.id_for_name("本")
        self.ch1 = self.col.decks.id_for_name("本::第1章")

    def tearDown(self):
        self.col.close()

    def inside(self, did):
        """The terms of the cards in a deck now."""
        there = self.col.db.list("select id from cards where did = ?", did)
        return sorted(t for t, i in self.ids.items() if i in there)

    def filtered(self, name, search, resched=False):
        """A filtered deck made by hand, or by another add-on."""
        deck = self.col.sched.get_or_create_filtered_deck(0)
        deck.name = name
        del deck.config.search_terms[:]
        deck.config.search_terms.append(FilteredDeckConfig.SearchTerm(search=search, limit=99, order=FilteredDeckConfig.SearchTerm.RANDOM))
        deck.config.reschedule = resched
        return self.col.sched.add_or_update_filtered_deck(deck).id

    def test_start_takes_the_deck_and_its_subdecks_less_suspended_and_buried(self):
        did = practice.start(self.col, self.book).id
        self.assertEqual(self.inside(did), sorted(FREE))             # not 近い (suspended), 遠い (buried), other
        deck = self.col.decks.get(did)
        self.assertEqual((deck["name"], deck["dyn"], deck["resched"]), ("Practice deck: 本", 1, False))
        self.assertEqual(practice.sessions(self.col), {did: self.book})
        self.assertEqual(practice.unfinished(self.col, self.book), {did: 6})
        self.assertEqual(self.col.undo_status().undo, "Practice deck 本")

    def test_a_subdeck_is_named_by_its_path_and_stays_at_the_top_level(self):
        did = practice.start(self.col, self.ch1).id
        self.assertEqual(self.col.decks.name(did), "Practice deck: 本 › 第1章")
        self.assertEqual(self.inside(did), sorted(("漢字", "読む", "書く", "話す")))

    def test_answering_leaves_every_card_as_it_was(self):
        before = cards(self.col)
        did = practice.start(self.col, self.book).id
        done = answer(self.col, did, [1, 2, 3, 4, 1, 2, 2, 1, 3])     # every button, some cards more than once
        self.assertGreater(len(done), len(FREE))
        self.assertEqual(set(done), {self.ids[t] for t in FREE})
        self.assertEqual(practice.left(self.col, did), 0)
        self.assertEqual(cards(self.col), before)
        log = self.col.db.all("select type, factor from revlog")
        self.assertEqual(len(log), len(done))
        self.assertEqual({tuple(r) for r in log}, {(3, 0)})          # filtered, no ease factor: FSRS leaves these out

    def test_with_fsrs_on_anki_only_fills_in_its_own_notes(self):
        cid, day = self.ids["漢字"], 86400000
        for ago, ease, ivl, kind in ((40, 3, 1, 0), (39, 3, 4, 1), (35, 3, 12, 1), (23, 2, 30, 1)):     # a real history
            self.col.db.execute("insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) values (?, ?, -1, ?, ?, 0, 2500, 5000, ?)",
                                int(time.time() * 1000) - ago * day, cid, ease, ivl, kind)
        self.col.set_config("fsrs", True)
        memory = self.col.compute_memory_state(cid)
        before = cards(self.col)
        answer(self.col, practice.start(self.col, self.book).id, [1, 2, 3, 4, 1, 2, 2, 1, 3])
        once = cards(self.col)
        self.assertEqual({i: r[:-1] for i, r in once.items()}, {i: r[:-1] for i, r in before.items()})   # all but the data
        read = json.loads(once[self.ids["読む"]][-1])                  # its memory state stays; the decay is added
        self.assertEqual((read["s"], read["d"], read["dr"]), (3.2, 5.1, 0.9))
        self.assertEqual(set(json.loads(once[self.ids["書く"]][-1])), {"decay"})                        # a new card: only the decay
        after = self.col.compute_memory_state(cid)                   # the practice answers don't count for FSRS
        self.assertEqual((after.stability, after.difficulty), (memory.stability, memory.difficulty))
        filled = json.loads(once[cid][-1])                           # it had none: the one its history gives it
        self.assertEqual((filled["s"], filled["d"]), (round(memory.stability, 4), round(memory.difficulty, 3)))
        answer(self.col, practice.start(self.col, self.book).id, [1, 2, 3, 4, 1, 2, 2, 1, 3])
        self.assertEqual(cards(self.col), once)                      # and with those in place, nothing changes

    def test_good_and_easy_send_a_card_home_and_again_and_hard_keep_it(self):
        did = practice.start(self.col, self.ch1).id
        self.col.decks.select(did)
        for ease, gone in ((1, 0), (2, 0), (3, 1), (4, 2)):
            answer_one(self.col, ease, ease)
            self.assertEqual(practice.left(self.col, did), 4 - gone, ease)

    def test_leaving_half_way_keeps_the_session_and_cleaning_up_leaves_it(self):
        before = cards(self.col)
        did = practice.start(self.col, self.book).id
        self.col.decks.select(did)
        for n in range(2):
            answer_one(self.col, 3, n)
        self.assertEqual(practice.unfinished(self.col, self.book), {did: 4})
        self.assertEqual(practice.finished(self.col), {})
        practice.clean_up(self.col)
        self.assertEqual(practice.sessions(self.col), {did: self.book})
        self.col.decks.remove([did])                                 # Anki's own Delete: the cards go home
        self.assertEqual(cards(self.col), before)

    def test_clean_up_removes_a_finished_session_and_no_cards(self):
        before = cards(self.col)
        did = practice.start(self.col, self.book).id
        other = practice.start(self.col, self.col.decks.id_for_name("Other")).id
        answer(self.col, did, [3])
        self.assertEqual(practice.finished(self.col), {did: self.book})
        out = practice.clean_up(self.col)
        self.assertEqual(out.count, 0)                               # cards deleted
        self.assertIsNone(self.col.decks.get(did, default=False))
        self.assertEqual(practice.sessions(self.col), {other: self.col.decks.id_for_name("Other")})
        self.col.decks.remove([other])
        self.assertEqual(cards(self.col), before)

    def test_starting_again_rebuilds_the_same_deck_with_every_card(self):
        did = practice.start(self.col, self.book).id
        self.col.decks.select(did)
        for n in range(3):
            answer_one(self.col, 3, n)
        self.assertLess(practice.left(self.col, did), 6)
        self.assertEqual(practice.start(self.col, self.book).id, did)
        self.assertEqual(self.inside(did), sorted(FREE))
        self.assertEqual(len(practice.sessions(self.col)), 1)

    def test_a_second_session_of_a_deck_is_removed_when_it_starts_again(self):
        did = practice.start(self.col, self.ch1).id
        self.col.decks.select(did)
        for n in range(2):
            answer_one(self.col, 3, n)
        twin = self.filtered("Practice deck: 本 › 第1章", f"did:{self.ch1}")     # as another device's: it takes the two that went home
        self.assertEqual(practice.unfinished(self.col, self.ch1), {did: 2, twin: 2})
        kept = practice.start(self.col, self.ch1).id
        self.assertEqual(practice.unfinished(self.col), {kept: 4})

    def test_a_deck_and_its_subdeck_each_have_a_session(self):
        before = cards(self.col)
        ch1 = practice.start(self.col, self.ch1).id
        book = practice.start(self.col, self.book).id                # takes what the chapter's session left
        self.assertEqual(self.inside(ch1), sorted(("漢字", "読む", "書く", "話す")))
        self.assertEqual(self.inside(book), sorted(("上手", "高い")))
        self.assertEqual(practice.sessions(self.col, self.book), {book: self.book})
        self.assertEqual(practice.start(self.col, self.ch1).id, ch1)  # and starting it again leaves the book's alone
        self.assertEqual(self.inside(book), sorted(("上手", "高い")))
        answer(self.col, ch1, [3])
        answer(self.col, book, [3])
        practice.clean_up(self.col)
        self.assertEqual(practice.sessions(self.col), {})
        self.assertEqual(cards(self.col), before)

    def test_nothing_to_practise_changes_nothing(self):
        self.col.sched.suspend_cards([self.ids["高い"]])
        ch2 = self.col.decks.id_for_name("本::第2章")
        undo = self.col.undo_status().undo
        with self.assertRaisesRegex(ValueError, "No cards to practise in 本::第2章"):
            practice.start(self.col, ch2)
        self.assertEqual(practice.sessions(self.col), {})
        self.assertEqual(self.col.undo_status().undo, undo)

    def test_undo_takes_the_session_back(self):
        before = cards(self.col)
        did = practice.start(self.col, self.book).id
        self.col.undo()
        self.assertIsNone(self.col.decks.get(did, default=False))
        self.assertEqual(cards(self.col), before)

    def test_a_renamed_deck_keeps_its_session(self):
        did = practice.start(self.col, self.ch1).id
        self.col.decks.rename(self.ch1, "本::だい1しょう")
        self.assertEqual(practice.sessions(self.col, self.ch1), {did: self.ch1})
        self.assertEqual(practice.start(self.col, self.ch1).id, did)
        self.assertEqual(self.col.decks.name(did), "Practice deck: 本 › だい1しょう")

    def test_other_filtered_decks_are_not_practice_decks(self):
        cid = self.ids["漢字"]
        self.filtered("Practice: 第1章", f"cid:{cid}")                         # Kyokasho's practice deck
        self.filtered("Practice deck: mine", "deck:本 is:new")                 # made by hand, on a search of its own
        self.filtered("Practice deck: study", f"did:{self.ch1}", resched=True)  # one that reschedules
        self.filtered("Cram", f"did:{self.book}")                              # not by its name
        self.assertEqual(practice.sessions(self.col), {})
        self.assertEqual(practice.finished(self.col), {})
        decks = len(self.col.decks.all_names_and_ids())
        practice.clean_up(self.col)
        self.assertEqual(len(self.col.decks.all_names_and_ids()), decks)

    def test_a_big_deck_is_taken_whole(self):
        basic = self.col.models.by_name("Basic")
        big = self.col.decks.id("Big")
        for i in range(1200):
            n = self.col.new_note(basic)
            n["Front"] = f"n{i}"
            self.col.add_note(n, big)
        did = practice.start(self.col, big).id
        self.assertEqual(practice.left(self.col, did), 1200)


if __name__ == "__main__":
    unittest.main()
