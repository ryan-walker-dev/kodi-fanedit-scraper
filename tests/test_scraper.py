"""
Unit tests for the pure-Python helpers and HTML parser in scraper.py.

These tests do NOT require a running Kodi instance; they stub out the
xbmc* modules so the scraper module can be imported in a standard Python
environment.
"""

import io
import json
import sys
import types
import unittest
import unittest.mock
import urllib.error

# ---------------------------------------------------------------------------
# Stub out Kodi modules so scraper.py can be imported without Kodi.
# ---------------------------------------------------------------------------

def _make_stub(name):
    mod = types.ModuleType(name)
    return mod


_xbmc = _make_stub("xbmc")
_xbmc.LOGINFO = 0
_xbmc.LOGERROR = 4
_xbmc.log = lambda *a, **kw: None


class _StubVideoInfoTag:
    def addAvailableArtwork(self, *a, **kw):
        pass


class _StubListItem:
    def __init__(self, *a, **kw):
        self._art = {}
        self._fanart = []
        self._tag = _StubVideoInfoTag()

    def getVideoInfoTag(self):
        return self._tag

    def setArt(self, art):
        self._art = art

    def setAvailableFanart(self, fanart_list):
        self._fanart = fanart_list

    def setProperty(self, *a, **kw):
        pass


class _StubDialog:
    def __init__(self):
        self.last_notification = None

    def notification(self, heading="", message="", icon=None, time=3000):
        self.last_notification = {"heading": heading, "message": message, "icon": icon}


_shared_dialog = _StubDialog()

_xbmcgui = _make_stub("xbmcgui")
_xbmcgui.NOTIFICATION_ERROR = "error"
_xbmcgui.ListItem = _StubListItem
_xbmcgui.Dialog = lambda: _shared_dialog

_xbmcplugin = _make_stub("xbmcplugin")
_xbmcplugin.endOfDirectory = lambda *a, **kw: None
_xbmcplugin.setResolvedUrl = lambda *a, **kw: None
_xbmcplugin.addDirectoryItems = lambda *a, **kw: None
_xbmcplugin.addDirectoryItem = lambda *a, **kw: None

_xbmcaddon = _make_stub("xbmcaddon")

for _name, _mod in [
    ("xbmc", _xbmc),
    ("xbmcgui", _xbmcgui),
    ("xbmcplugin", _xbmcplugin),
    ("xbmcaddon", _xbmcaddon),
]:
    sys.modules[_name] = _mod

# Now we can safely import from scraper.py
from scraper import (  # noqa: E402
    _clean_html,
    _extract_year,
    _parse_runtime_minutes,
    FaneditScraper,
)


# ---------------------------------------------------------------------------
# Tests for _clean_html
# ---------------------------------------------------------------------------

class TestCleanHtml(unittest.TestCase):

    def test_strips_tags(self):
        self.assertEqual(_clean_html("<b>Hello</b>"), "Hello")

    def test_decodes_amp(self):
        self.assertEqual(_clean_html("A &amp; B"), "A & B")

    def test_decodes_lt_gt(self):
        self.assertEqual(_clean_html("&lt;tag&gt;"), "<tag>")

    def test_decodes_numeric_entity(self):
        # &#160; is non-breaking space (chr 160)
        result = _clean_html("foo&#160;bar")
        self.assertIn("bar", result)

    def test_collapses_whitespace(self):
        self.assertEqual(_clean_html("  foo   bar  "), "foo bar")

    def test_nested_tags(self):
        self.assertEqual(_clean_html("<div><p>Hello <span>World</span></p></div>"), "Hello World")

    def test_empty_string(self):
        self.assertEqual(_clean_html(""), "")

    def test_decodes_apos_entity(self):
        self.assertEqual(_clean_html("It&#39;sOnRandom"), "It'sOnRandom")


# ---------------------------------------------------------------------------
# Tests for _extract_year
# ---------------------------------------------------------------------------

class TestExtractYear(unittest.TestCase):

    def test_finds_year(self):
        self.assertEqual(_extract_year("Released in 2019."), "2019")

    def test_prefers_first_year(self):
        self.assertEqual(_extract_year("2015 and 2020"), "2015")

    def test_no_year(self):
        self.assertEqual(_extract_year("No year here."), "")

    def test_rejects_too_old(self):
        # Years before 1950 should not match
        self.assertEqual(_extract_year("Year 1900"), "")

    def test_rejects_too_new(self):
        # Years beyond 2039 should not match
        self.assertEqual(_extract_year("Year 2050"), "")

    def test_year_in_parentheses(self):
        self.assertEqual(_extract_year("The Matrix (1999)"), "1999")

    def test_year_2000(self):
        self.assertEqual(_extract_year("Made in 2000"), "2000")

    def test_month_year_text(self):
        self.assertEqual(_extract_year("December 2020"), "2020")


# ---------------------------------------------------------------------------
# Tests for _parse_runtime_minutes
# ---------------------------------------------------------------------------

class TestParseRuntimeMinutes(unittest.TestCase):

    def test_minutes_only(self):
        self.assertEqual(_parse_runtime_minutes("120 min"), 120)

    def test_minutes_word(self):
        self.assertEqual(_parse_runtime_minutes("90 minutes"), 90)

    def test_hours_and_minutes(self):
        self.assertEqual(_parse_runtime_minutes("2h 30m"), 150)

    def test_hours_and_minutes_long(self):
        self.assertEqual(_parse_runtime_minutes("2 hours 15 minutes"), 135)

    def test_colon_format(self):
        self.assertEqual(_parse_runtime_minutes("1:45"), 105)

    def test_colon_format_with_seconds(self):
        self.assertEqual(_parse_runtime_minutes("2:00:00"), 120)

    def test_hours_only(self):
        self.assertEqual(_parse_runtime_minutes("3 hours"), 180)

    def test_no_runtime(self):
        self.assertEqual(_parse_runtime_minutes("No runtime here"), 0)

    def test_empty_string(self):
        self.assertEqual(_parse_runtime_minutes(""), 0)

    def test_117_minutes(self):
        self.assertEqual(_parse_runtime_minutes("117 minutes"), 117)


# ---------------------------------------------------------------------------
# Tests for FaneditScraper._is_fanedit_detail_page
# ---------------------------------------------------------------------------

class TestIsFaneditDetailPage(unittest.TestCase):

    def test_accepts_simple_fanedit_url(self):
        self.assertTrue(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/mr-white/"
        ))

    def test_accepts_fanedit_subpath(self):
        self.assertTrue(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/fanedits/mr-white/"
        ))

    def test_rejects_category_page(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/category/drama/"
        ))

    def test_rejects_tag_page(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/tag/action/"
        ))

    def test_rejects_author_page(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/author/johndoe/"
        ))

    def test_rejects_non_fanedit_domain(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.example.com/some-movie/"
        ))

    def test_rejects_bare_domain(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/"
        ))

    def test_rejects_search_page(self):
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(
            "https://www.fanedit.org/search?q=mr+white"
        ))


# ---------------------------------------------------------------------------
# Tests for FaneditScraper._parse_fanedit_page
# ---------------------------------------------------------------------------

class TestParseFaneditPage(unittest.TestCase):
    """
    Test the HTML parser against a realistic fanedit.org page structure.

    The HTML below mirrors the actual JReviews-based layout used on
    fanedit.org, including:
      - <h1 class="contentheading"><span itemprop="headline">
      - <meta itemprop="image" content="...">
      - JReviews custom-field divs (jrFaneditorname, jrOriginalmovietitle, etc.)
      - Schema.org aggregateRating microdata
    """

    SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en-US">
<head>
<title>Mr White - Fanedit.org</title>
<meta itemprop="image" content="https://ifdbphoto.tor1.cdn.digitaloceanspaces.com/original/01/a4/35/mrwhite-front-64-1608508666.jpg">
</head>
<body>
<h1 class="contentheading">
    <span itemprop="headline">Mr White</span>
</h1>

<div class="jrCustomFields">
  <div class="jrFieldGroup basic-details">

    <div class="jrFaneditorname jrFieldRow">
      <div class="jrFieldLabel">Faneditor Name:</div>
      <div class="jrFieldValue">
        <ul class="jrFieldValueList">
          <li><a href="/fanedit-search/tag/faneditorname/it-sonrandom/?criteria=2">It&#39;sOnRandom</a></li>
        </ul>
      </div>
    </div>

    <div class="jrOriginalmovietitle jrFieldRow">
      <div class="jrFieldLabel">Original Movie/Show Title:</div>
      <div class="jrFieldValue">
        <ul class="jrFieldValueList">
          <li><a href="/fanedit-search/tag/originalmovietitle/breaking-bad/?criteria=2">Breaking Bad</a></li>
        </ul>
      </div>
    </div>

    <div class="jrGenre jrFieldRow">
      <div class="jrFieldLabel">Genre:</div>
      <div class="jrFieldValue">
        <ul class="jrFieldValueList">
          <li><a href="/fanedit-search/tag/genre/action/?criteria=2">Action</a></li>
        </ul>
      </div>
    </div>

    <div class="jrFanedittype jrFieldRow">
      <div class="jrFieldLabel">Fanedit Type:</div>
      <div class="jrFieldValue">
        <a href="/fanedit-search/tag/fanedittype/tv-to-movie/?criteria=2">TV-to-Movie</a>
      </div>
    </div>

    <div class="jrOriginalreleasedate jrFieldRow">
      <div class="jrFieldLabel">Original Release Date:</div>
      <div class="jrFieldValue">2008</div>
    </div>

    <div class="jrFaneditreleasedate jrFieldRow">
      <div class="jrFieldLabel">Fanedit Release Date:</div>
      <div class="jrFieldValue">
        <a href="/fanedit-search/tag/faneditreleasedate/December+2020/?criteria=2">December 2020</a>
      </div>
    </div>

    <div class="jrFaneditrunningtimemin jrFieldRow">
      <div class="jrFieldLabel">Fanedit Running Time:</div>
      <div class="jrFieldValue">117 minutes</div>
    </div>

  </div>

  <div class="jrFieldGroup fanedit-information">

    <div class="jrBriefsynopsis jrFieldRow">
      <div class="jrFieldLabel">Synopsis:</div>
      <div class="jrFieldValue">A shortened down TV to Movie edit of the first season of Breaking Bad</div>
    </div>

    <div class="jrIntention jrFieldRow">
      <div class="jrFieldLabel">Intention:</div>
      <div class="jrFieldValue">Make a version of Season 1 of Breaking Bad into a film for a much easier watch</div>
    </div>

  </div>
</div>

<!-- Schema.org aggregate rating -->
<div class="jrRoundedPanel jrReview jrUserReviewsSummary"
     itemprop="aggregateRating" itemscope="" itemtype="https://schema.org/AggregateRating">
  <div class="jrUserReviewsSummaryTitle">
    <span itemprop="reviewCount">14</span> reviews
  </div>
  <div itemprop="ratingValue" class="jrRatingValue">9.6</div>
  <meta itemprop="bestRating" content="10">
</div>

</body>
</html>"""

    def setUp(self):
        self.details = FaneditScraper._parse_fanedit_page(
            self.SAMPLE_HTML, "https://www.fanedit.org/mr-white/"
        )

    # --- Identity --------------------------------------------------------

    def test_fanedit_id_from_url(self):
        self.assertEqual(self.details["fanedit_id"], "mr-white")

    # --- Title -----------------------------------------------------------

    def test_title_extracted(self):
        self.assertEqual(self.details["title"], "Mr White")

    def test_title_strips_site_suffix(self):
        """Title should not include '- Fanedit.org' suffix."""
        self.assertNotIn("Fanedit.org", self.details["title"])

    # --- Poster ----------------------------------------------------------

    def test_poster_extracted(self):
        self.assertIn("mrwhite-front-64-1608508666.jpg", self.details["poster"])

    # --- Editor ----------------------------------------------------------

    def test_editor_extracted(self):
        self.assertEqual(self.details["editor"], "It'sOnRandom")

    # --- Original title --------------------------------------------------

    def test_original_title_extracted(self):
        self.assertEqual(self.details["original_title"], "Breaking Bad")

    # --- Genre -----------------------------------------------------------

    def test_genre_extracted(self):
        self.assertIn("Action", self.details["genres"])

    # --- Fanedit type ----------------------------------------------------

    def test_fanedit_type_extracted(self):
        self.assertEqual(self.details["fanedit_type"], "TV-to-Movie")

    # --- Year ------------------------------------------------------------

    def test_year_is_fanedit_release_year(self):
        """Year should reflect the fanedit release (2020), not original (2008)."""
        self.assertEqual(self.details["year"], 2020)

    # --- Runtime ---------------------------------------------------------

    def test_runtime_extracted(self):
        self.assertEqual(self.details["runtime"], 117)

    # --- Plot ------------------------------------------------------------

    def test_plot_contains_synopsis(self):
        self.assertIn("Breaking Bad", self.details["plot"])

    def test_plot_contains_intention(self):
        self.assertIn("film", self.details["plot"])

    # --- Ratings ---------------------------------------------------------

    def test_rating_extracted(self):
        self.assertAlmostEqual(self.details["rating"], 9.6)

    def test_votes_extracted(self):
        self.assertEqual(self.details["votes"], 14)

    # --- Robustness ------------------------------------------------------

    def test_minimal_page_does_not_crash(self):
        """Parser must not raise on a nearly-empty page."""
        result = FaneditScraper._parse_fanedit_page(
            "<html><head><title>Test - Fanedit.org</title></head>"
            "<body><h1 class=\"contentheading\">"
            "<span itemprop=\"headline\">Test Edit</span></h1></body></html>",
            "https://www.fanedit.org/test-edit/",
        )
        self.assertEqual(result["title"], "Test Edit")
        self.assertNotIn("plot", result)
        self.assertNotIn("poster", result)
        self.assertNotIn("editor", result)

    def test_title_fallback_to_title_tag(self):
        """When contentheading is absent, fall back to <title> tag."""
        html = "<html><head><title>Some Edit - Fanedit.org</title></head><body></body></html>"
        result = FaneditScraper._parse_fanedit_page(html, "https://www.fanedit.org/some-edit/")
        self.assertEqual(result.get("title"), "Some Edit")


# ---------------------------------------------------------------------------
# Helpers shared by integration-style tests
# ---------------------------------------------------------------------------

def _make_addon(api_key="test-key", cx="test-cx", max_results="10"):
    """Return a minimal addon stub with preset settings."""
    addon = unittest.mock.MagicMock()
    addon.getSetting.side_effect = lambda key: {
        "google_api_key": api_key,
        "google_cx": cx,
        "max_results": max_results,
    }.get(key, "")
    return addon


# ---------------------------------------------------------------------------
# Tests for find_movie error-path notifications
# ---------------------------------------------------------------------------

class TestFindMovieNotifications(unittest.TestCase):
    """Verify that user-facing notifications are shown on API error paths."""

    def setUp(self):
        # Reset the shared dialog state before each test
        _shared_dialog.last_notification = None

    def test_missing_api_key_shows_notification(self):
        scraper = FaneditScraper(_make_addon(api_key="", cx="test-cx"))
        scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        self.assertIn("not set", _shared_dialog.last_notification["message"])

    def test_missing_cx_shows_notification(self):
        scraper = FaneditScraper(_make_addon(api_key="test-key", cx=""))
        scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        self.assertIn("not set", _shared_dialog.last_notification["message"])

    def test_http_error_shows_notification(self):
        scraper = FaneditScraper(_make_addon())
        http_exc = urllib.error.HTTPError(
            url="https://example.com", code=403, msg="Forbidden",
            hdrs=None, fp=io.BytesIO(b'{"error": {"message": "API key invalid"}}'),
        )
        with unittest.mock.patch("urllib.request.urlopen", side_effect=http_exc):
            scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        msg = _shared_dialog.last_notification["message"]
        self.assertIn("403", msg)

    def test_url_error_shows_notification(self):
        scraper = FaneditScraper(_make_addon())
        url_exc = urllib.error.URLError(reason="Name or service not known")
        with unittest.mock.patch("urllib.request.urlopen", side_effect=url_exc):
            scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        msg = _shared_dialog.last_notification["message"]
        self.assertIn("connection failed", msg.lower())

    def test_notification_icon_is_error(self):
        scraper = FaneditScraper(_make_addon(api_key="", cx=""))
        scraper.find_movie(handle=1, title="Test")
        self.assertEqual(_shared_dialog.last_notification["icon"], _xbmcgui.NOTIFICATION_ERROR)


# ---------------------------------------------------------------------------
# Tests for get_artwork
# ---------------------------------------------------------------------------

class TestGetArtwork(unittest.TestCase):
    """Verify get_artwork dispatches correctly."""

    _MINIMAL_HTML = """<!DOCTYPE html>
<html><head>
<title>Test Edit - Fanedit.org</title>
<meta itemprop="image" content="https://example.com/poster.jpg">
</head><body>
<h1 class="contentheading"><span itemprop="headline">Test Edit</span></h1>
</body></html>"""

    def test_empty_id_calls_setResolvedUrl_false(self):
        scraper = FaneditScraper(_make_addon())
        calls = []
        with unittest.mock.patch.object(_xbmcplugin, "setResolvedUrl",
                                        side_effect=lambda h, s, li: calls.append(s)):
            scraper.get_artwork(handle=1, fanedit_id="")
        self.assertEqual(calls, [False])

    def test_fetch_error_calls_setResolvedUrl_false(self):
        scraper = FaneditScraper(_make_addon())
        url_exc = urllib.error.URLError(reason="Connection refused")
        calls = []
        with unittest.mock.patch("urllib.request.urlopen", side_effect=url_exc):
            with unittest.mock.patch.object(_xbmcplugin, "setResolvedUrl",
                                            side_effect=lambda h, s, li: calls.append(s)):
                scraper.get_artwork(handle=1, fanedit_id="test-edit")
        self.assertEqual(calls, [False])

    def test_successful_fetch_calls_setResolvedUrl_true(self):
        scraper = FaneditScraper(_make_addon())
        fake_response = unittest.mock.MagicMock()
        fake_response.read.return_value = self._MINIMAL_HTML.encode("utf-8")
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = unittest.mock.MagicMock(return_value=False)
        calls = []
        with unittest.mock.patch("urllib.request.urlopen", return_value=fake_response):
            with unittest.mock.patch.object(_xbmcplugin, "setResolvedUrl",
                                            side_effect=lambda h, s, li: calls.append(s)):
                scraper.get_artwork(handle=1, fanedit_id="test-edit")
        self.assertEqual(calls, [True])

    def test_poster_added_as_artwork(self):
        scraper = FaneditScraper(_make_addon())
        fake_response = unittest.mock.MagicMock()
        fake_response.read.return_value = self._MINIMAL_HTML.encode("utf-8")
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = unittest.mock.MagicMock(return_value=False)
        artwork_calls = []
        original_add = _StubVideoInfoTag.addAvailableArtwork

        def capture_artwork(self_tag, url, art_type):
            artwork_calls.append((url, art_type))

        with unittest.mock.patch.object(_StubVideoInfoTag, "addAvailableArtwork", capture_artwork):
            with unittest.mock.patch("urllib.request.urlopen", return_value=fake_response):
                with unittest.mock.patch.object(_xbmcplugin, "setResolvedUrl", lambda *a: None):
                    scraper.get_artwork(handle=1, fanedit_id="test-edit")

        self.assertTrue(any(art_type == "poster" for _, art_type in artwork_calls))


if __name__ == "__main__":
    unittest.main()
