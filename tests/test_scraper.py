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
    def __init__(self):
        self._title = ""

    def addAvailableArtwork(self, *a, **kw):
        pass

    def setTitle(self, title):
        self._title = title

    def getTitle(self):
        return self._title

    def setYear(self, *a, **kw):
        pass

    def setPlot(self, *a, **kw):
        pass

    def setOriginalTitle(self, *a, **kw):
        pass

    def setTagLine(self, *a, **kw):
        pass

    def setDuration(self, *a, **kw):
        pass

    def setDirectors(self, *a, **kw):
        pass

    def setWriters(self, *a, **kw):
        pass

    def setGenres(self, *a, **kw):
        pass

    def setRating(self, *a, **kw):
        pass

    def setUniqueID(self, *a, **kw):
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
        self.select_return = 0  # default: selects the first item

    def notification(self, heading="", message="", icon=None, time=3000):
        self.last_notification = {"heading": heading, "message": message, "icon": icon}

    def select(self, heading="", options=None):
        return self.select_return


_shared_dialog = _StubDialog()

_xbmcgui = _make_stub("xbmcgui")
_xbmcgui.NOTIFICATION_ERROR = "error"
_xbmcgui.NOTIFICATION_WARNING = "warning"
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

def _make_addon(max_results="10"):
    """Return a minimal addon stub with preset settings."""
    addon = unittest.mock.MagicMock()
    addon.getSetting.side_effect = lambda key: {
        "max_results": max_results,
    }.get(key, "")
    return addon


# Minimal HTML search results pages used by find_movie tests.
_SEARCH_HTML_ONE_RESULT = """<!DOCTYPE html>
<html><body>
<article>
  <h2><a href="https://www.fanedit.org/star-wars-de-specialized/">Star Wars: De-Specialized Edition</a></h2>
  <img src="https://example.com/thumb.jpg">
  <p>A restoration of the original trilogy.</p>
</article>
</body></html>"""

_SEARCH_HTML_TWO_RESULTS = """<!DOCTYPE html>
<html><body>
<article>
  <h2><a href="https://www.fanedit.org/star-wars-a/">Star Wars: Edit A</a></h2>
  <p>First edit.</p>
</article>
<article>
  <h2><a href="https://www.fanedit.org/star-wars-b/">Star Wars: Edit B</a></h2>
  <p>Second edit.</p>
</article>
</body></html>"""

_SEARCH_HTML_NO_RESULTS = """<!DOCTYPE html>
<html><body><p>No results found.</p></body></html>"""


# ---------------------------------------------------------------------------
# Tests for find_movie error-path notifications
# ---------------------------------------------------------------------------

class TestFindMovieNotifications(unittest.TestCase):
    """Verify that user-facing notifications are shown on error/no-result paths."""

    def setUp(self):
        # Reset the shared dialog state before each test
        _shared_dialog.last_notification = None
        _shared_dialog.select_return = 0

    def _fake_response(self, html):
        resp = unittest.mock.MagicMock()
        resp.read.return_value = html.encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = unittest.mock.MagicMock(return_value=False)
        return resp

    def test_http_error_shows_notification(self):
        scraper = FaneditScraper(_make_addon())
        http_exc = urllib.error.HTTPError(
            url="https://fanedit.org", code=503, msg="Service Unavailable",
            hdrs=None, fp=io.BytesIO(b""),
        )
        with unittest.mock.patch("urllib.request.urlopen", side_effect=http_exc):
            scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        self.assertIn("503", _shared_dialog.last_notification["message"])

    def test_url_error_shows_notification(self):
        scraper = FaneditScraper(_make_addon())
        url_exc = urllib.error.URLError(reason="Name or service not known")
        with unittest.mock.patch("urllib.request.urlopen", side_effect=url_exc):
            scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)
        self.assertIn("connection failed", _shared_dialog.last_notification["message"].lower())

    def test_notification_icon_is_error_on_http_failure(self):
        scraper = FaneditScraper(_make_addon())
        http_exc = urllib.error.HTTPError(
            url="https://fanedit.org", code=403, msg="Forbidden",
            hdrs=None, fp=io.BytesIO(b""),
        )
        with unittest.mock.patch("urllib.request.urlopen", side_effect=http_exc):
            scraper.find_movie(handle=1, title="Test")
        self.assertEqual(_shared_dialog.last_notification["icon"], _xbmcgui.NOTIFICATION_ERROR)

    def test_no_results_shows_notification(self):
        scraper = FaneditScraper(_make_addon())
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=self._fake_response(_SEARCH_HTML_NO_RESULTS)):
            scraper.find_movie(handle=1, title="Star Wars")
        self.assertIsNotNone(_shared_dialog.last_notification)

    def test_single_result_calls_endOfDirectory_true(self):
        scraper = FaneditScraper(_make_addon())
        calls = []
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=self._fake_response(_SEARCH_HTML_ONE_RESULT)):
            with unittest.mock.patch.object(
                _xbmcplugin, "endOfDirectory",
                side_effect=lambda h, succeeded: calls.append(succeeded),
            ):
                scraper.find_movie(handle=1, title="Star Wars")
        self.assertIn(True, calls)

    def test_multiple_results_dialog_cancel_ends_with_false(self):
        scraper = FaneditScraper(_make_addon())
        _shared_dialog.select_return = -1  # simulate user cancelling the dialog
        calls = []
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=self._fake_response(_SEARCH_HTML_TWO_RESULTS)):
            with unittest.mock.patch.object(
                _xbmcplugin, "endOfDirectory",
                side_effect=lambda h, succeeded: calls.append(succeeded),
            ):
                scraper.find_movie(handle=1, title="Star Wars")
        self.assertIn(False, calls)
        self.assertNotIn(True, calls)

    def test_multiple_results_dialog_selection_ends_with_true(self):
        scraper = FaneditScraper(_make_addon())
        _shared_dialog.select_return = 0  # select the first result
        calls = []
        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=self._fake_response(_SEARCH_HTML_TWO_RESULTS)):
            with unittest.mock.patch.object(
                _xbmcplugin, "endOfDirectory",
                side_effect=lambda h, succeeded: calls.append(succeeded),
            ):
                scraper.find_movie(handle=1, title="Star Wars")
        self.assertIn(True, calls)


# ---------------------------------------------------------------------------
# Tests for FaneditScraper._parse_search_results
# ---------------------------------------------------------------------------

class TestParseSearchResults(unittest.TestCase):
    """Test the HTML search results parser."""

    def test_parses_single_article(self):
        html = """<html><body>
<article>
  <h2><a href="https://www.fanedit.org/star-wars-edit/">Star Wars: The Edit</a></h2>
  <img src="https://example.com/thumb.jpg">
  <p>A great fan edit.</p>
</article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        self.assertEqual(len(results), 1)
        url, title, thumbnail, snippet = results[0]
        self.assertEqual(url, "https://www.fanedit.org/star-wars-edit/")
        self.assertIn("Star Wars", title)
        self.assertEqual(thumbnail, "https://example.com/thumb.jpg")
        self.assertIn("fan edit", snippet)

    def test_strips_site_suffix_from_title(self):
        html = """<html><body>
<article>
  <h2><a href="https://www.fanedit.org/edit/">Some Edit | Fanedit.org</a></h2>
</article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        self.assertEqual(len(results), 1)
        self.assertNotIn("Fanedit.org", results[0][1])

    def test_empty_page_returns_empty_list(self):
        results = FaneditScraper._parse_search_results(
            "<html><body><p>Nothing here.</p></body></html>"
        )
        self.assertEqual(results, [])

    def test_multiple_articles_returns_all(self):
        html = """<html><body>
<article><h2><a href="https://www.fanedit.org/edit-a/">Edit A</a></h2></article>
<article><h2><a href="https://www.fanedit.org/edit-b/">Edit B</a></h2></article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        self.assertEqual(len(results), 2)

    def test_heading_title_preferred_over_link_text(self):
        html = """<html><body>
<article>
  <h2>Heading Title</h2>
  <a href="https://www.fanedit.org/some-edit/">Link Text</a>
</article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], "Heading Title")
        self.assertEqual(results[0][0], "https://www.fanedit.org/some-edit/")

    def test_skips_relative_links(self):
        html = """<html><body>
<article>
  <h2><a href="/relative/path/">Relative Link Edit</a></h2>
</article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        self.assertEqual(results, [])

    def test_non_fanedit_absolute_url_is_included_but_filterable(self):
        """_parse_search_results returns all absolute http URLs; callers use
        _is_fanedit_detail_page to filter out non-fanedit results."""
        html = """<html><body>
<article>
  <h2><a href="https://www.example.com/some-edit/">External Edit</a></h2>
</article>
</body></html>"""
        results = FaneditScraper._parse_search_results(html)
        # The parser accepts it; it is the caller's responsibility to filter
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "https://www.example.com/some-edit/")
        # Confirm _is_fanedit_detail_page would correctly reject it
        self.assertFalse(FaneditScraper._is_fanedit_detail_page(results[0][0]))

    # ------------------------------------------------------------------
    # JReviews listing format (current fanedit.org search results layout)
    # ------------------------------------------------------------------

    # Minimal JReviews listing block mirroring the real fanedit.org HTML.
    _JREVIEWS_SINGLE = """<html><body>
\t\t\t\t\t\t<a href="https://fanedit.org/cosmogony/"><img></a>
\t\t\t\t\t\t<a href="https://fanedit.org/cosmogony/">Cosmogony</a>
\t\t\t\t\t\tFanMix
\t\t\t\t\t\tFaneditor Name:<ul><li><a href="/fanedit-search/tag/faneditorname/tmbtm/?criteria=2">The Man Behind The Mask</a></li></ul>Fanedit Type:<a href="/fanedit-search/tag/fanedittype/fanmix/?criteria=2">FanMix</a>Fanedit Running Time:122 minutesSynopsis:Cosmogony is a fanedit about humanity and nature.
\t\t\t\t\t\t<input id="listing886" data-location=""
                data-listingurl="https://fanedit.org/cosmogony/" data-thumburl="https://ifdbphoto.example.com/Cosmogony-front.jpg"
                data-listingtitle="Cosmogony" data-listingid="listing886"
                data-listingtypeid="2" data-listingtypetitle="Fanedit Details"
                value="886" />
\t\t\t\t\t\t<a href="https://fanedit.org/cosmogony/">Read more</a>
</body></html>"""

    _JREVIEWS_TWO = """<html><body>
\t\t\t\t\t\t<a href="https://fanedit.org/edit-a/">Edit A</a>
\t\t\t\t\t\tSynopsis:First edit synopsis.
\t\t\t\t\t\t<input id="listing1"
                data-listingurl="https://fanedit.org/edit-a/" data-thumburl="https://example.com/thumb-a.jpg"
                data-listingtitle="Edit A" data-listingid="listing1" value="1" />
\t\t\t\t\t\t<a href="https://fanedit.org/edit-b/">Edit B</a>
\t\t\t\t\t\tSynopsis:Second edit synopsis.
\t\t\t\t\t\t<input id="listing2"
                data-listingurl="https://fanedit.org/edit-b/" data-thumburl="https://example.com/thumb-b.jpg"
                data-listingtitle="Edit B" data-listingid="listing2" value="2" />
</body></html>"""

    def test_parses_jreviews_listing_input(self):
        """Primary strategy extracts URL and title from data-* attributes."""
        results = FaneditScraper._parse_search_results(self._JREVIEWS_SINGLE)
        self.assertEqual(len(results), 1)
        url, title, thumbnail, snippet = results[0]
        self.assertEqual(url, "https://fanedit.org/cosmogony/")
        self.assertEqual(title, "Cosmogony")

    def test_jreviews_extracts_thumbnail_from_data_thumburl(self):
        """Thumbnail is taken from the data-thumburl attribute."""
        results = FaneditScraper._parse_search_results(self._JREVIEWS_SINGLE)
        _, _, thumbnail, _ = results[0]
        self.assertEqual(thumbnail, "https://ifdbphoto.example.com/Cosmogony-front.jpg")

    def test_jreviews_extracts_synopsis_as_snippet(self):
        """Snippet is extracted from the inline 'Synopsis:' field."""
        results = FaneditScraper._parse_search_results(self._JREVIEWS_SINGLE)
        _, _, _, snippet = results[0]
        self.assertIn("humanity", snippet)

    def test_jreviews_multiple_listings(self):
        """All JReviews listing inputs are parsed into separate results."""
        results = FaneditScraper._parse_search_results(self._JREVIEWS_TWO)
        self.assertEqual(len(results), 2)
        urls = [r[0] for r in results]
        self.assertIn("https://fanedit.org/edit-a/", urls)
        self.assertIn("https://fanedit.org/edit-b/", urls)

    def test_jreviews_preferred_over_article_strategy(self):
        """When data-listingurl inputs are present, article strategy is skipped."""
        html = self._JREVIEWS_SINGLE + """
<article>
  <h2><a href="https://www.fanedit.org/article-edit/">Article Edit</a></h2>
</article>"""
        results = FaneditScraper._parse_search_results(html)
        urls = [r[0] for r in results]
        # JReviews result is present
        self.assertIn("https://fanedit.org/cosmogony/", urls)
        # Article-strategy result is NOT present (JReviews took priority)
        self.assertNotIn("https://www.fanedit.org/article-edit/", urls)


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
