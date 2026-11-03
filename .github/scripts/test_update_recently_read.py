import unittest

from update_recently_read import END_TAG, START_TAG, update_recent


README = f"Current list stays\n{START_TAG}\nOld list\n{END_TAG}\nFooter\n"
SAVED = [
    {"id": str(index), "title": f"Book {index}", "author": "Author", "url": f"https://www.goodreads.com/book/show/{index}", "finished": date, "rating": 4}
    for index, date in [(1, "2026-10-26"), (2, "2026-09-18"), (3, "2026-09-16")]
]


def event(book_id, action, timestamp="October 21, 2026 08:19", stars=""):
    return f"""<tr class="update" data-timestamp="{timestamp}"><td>
    <div class="updateAction"><strong>Arti</strong> {action}{stars}</div>
    <a class="bookTitle" href="/book/show/{book_id}-title">Book {book_id}</a>
    <a class="authorName">Author</a>
    <table><tr><td><div class="stars" data-rating="0">Viewer's rating</div></td></tr></table>
    </td></tr>"""


class UpdateRecentlyReadTests(unittest.TestCase):
    def test_merges_by_completion_date_retains_history_and_is_idempotent(self):
        html = event(4, "finished reading") + event(5, "started reading")
        updated, recent = update_recent(README, SAVED, html)
        self.assertEqual([book["id"] for book in recent], ["1", "4", "2"])
        self.assertTrue(updated.startswith("Current list stays\n"))
        self.assertTrue(updated.endswith("\nFooter\n"))
        self.assertEqual(update_recent(updated, recent, html), (updated, recent))
        self.assertEqual(SAVED[0]["rating"], 4)

    def test_ratings_do_not_qualify_unfinished_books_or_reorder_finished_books(self):
        stars = '<span class="staticStars" title="liked it"><span class="staticStar p10"></span></span>'
        html = event(8, "rated a book", stars=stars) + event(8, "did not finish") + event(2, "rated a book", stars=stars)
        updated, recent = update_recent(README, SAVED, html)
        self.assertEqual([book["id"] for book in recent], ["1", "2", "3"])
        self.assertEqual(recent[1]["rating"], 3)
        self.assertIn("⭐ 3/5", updated)
        self.assertNotIn("Book 8", updated)

    def test_replayed_old_completion_cannot_replace_newer_finish(self):
        _, recent = update_recent(README, SAVED, event(1, "finished reading"))
        self.assertEqual(recent[0]["finished"], "2026-10-26")

    def test_rejects_sign_in_and_invalid_markers(self):
        with self.assertRaises(ValueError):
            update_recent(README, SAVED, "<title>Sign in</title>")
        with self.assertRaises(ValueError):
            update_recent("Missing markers", SAVED, event(4, "finished reading"))


if __name__ == "__main__":
    unittest.main()
