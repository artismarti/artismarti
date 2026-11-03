import unittest

from update_currently_reading import END_TAG, START_TAG, update_readme


README = f"Before\n{START_TAG}\nOld book\n{END_TAG}\nRecently read stays here\n"
HTML = """
<a class="bookTitle" href="/book/show/1">Outside section</a>
<div id="currentlyReadingReviews"><div>
<a class="bookTitle" href="/book/show/123-orbital">Orbital &amp; [Other]</a>
<div><a class="authorName">Samantha <span>Harvey</span></a></div>
</div></div>
<a class="bookTitle" href="/book/show/2">Outside section</a>
"""


class UpdateCurrentlyReadingTests(unittest.TestCase):
    def test_updates_only_currently_reading_and_escapes_copy(self):
        updated = update_readme(README, HTML)
        self.assertEqual(
            updated,
            f"Before\n{START_TAG}\n"
            "- [Orbital & \\[Other\\]](https://www.goodreads.com/book/show/123-orbital) by Samantha Harvey\n"
            f"{END_TAG}\nRecently read stays here\n",
        )
        self.assertEqual(update_readme(updated, HTML), updated)

    def test_rejects_sign_in_and_changed_markup(self):
        for html in ["<title>Sign in</title>", '<div id="currentlyReadingReviews"></div>', HTML.replace("authorName", "changed")]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                update_readme(README, html)

    def test_rejects_invalid_markers(self):
        for readme in ["No markers", README + END_TAG, f"{END_TAG}{START_TAG}"]:
            with self.subTest(readme=readme), self.assertRaises(ValueError):
                update_readme(readme, HTML)


if __name__ == "__main__":
    unittest.main()
