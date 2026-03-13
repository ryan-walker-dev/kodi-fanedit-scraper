"""
Core scraper module for the Fanedit.org Kodi metadata scraper.

Search flow
-----------
1. User triggers a library scan / manual info search in Kodi.
2. Kodi calls ``find_movie`` with the title (and optional year).
3. This module queries the Google Custom Search API restricted to fanedit.org.
4. Matching fanedit.org pages are returned as Kodi ListItems so the user
   can select the correct entry.
5. Kodi calls ``get_details`` with the chosen URL.
6. The page is fetched and parsed; all available metadata is returned via
   a Kodi ListItem.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcplugin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADDON_ID = "metadata.fanedit.org"
GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
FANEDIT_BASE_URL = "https://www.fanedit.org"

# Kodi log-level aliases (kept explicit for readability)
_LOG_INFO = xbmc.LOGINFO
_LOG_ERROR = xbmc.LOGERROR

_USER_AGENT = "Kodi/21 Fanedit.org-Scraper/1.0 (https://github.com/ryan-walker-dev/kodi-fanedit-scraper)"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _log(msg: str, level: int = _LOG_INFO) -> None:
    xbmc.log(f"[{ADDON_ID}] {msg}", level)


def _clean_html(text: str) -> str:
    """Strip HTML tags, collapse whitespace, and decode common entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&apos;": "'",
        "&nbsp;": " ", "&#8211;": "–", "&#8212;": "—",
        "&#8216;": "'", "&#8217;": "'", "&#8220;": '"', "&#8221;": '"',
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    # Numeric decimal entities (e.g. &#160;)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return text


def _extract_year(text: str) -> str:
    """Return the first plausible 4-digit year found in *text*, or ''."""
    match = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", text)
    return match.group(0) if match else ""


def _parse_runtime_minutes(text: str) -> int:
    """
    Parse runtime from a string that may contain patterns like:
      '120 min', '2h 30m', '2:30', '2 hours 30 minutes'
    Returns minutes as an int, or 0 if not found.
    """
    # e.g. "2 hours 30 minutes" / "2h 30m"
    hm = re.search(r"(\d+)\s*h(?:ours?)?\s*(\d+)\s*m(?:in(?:utes?)?)?", text, re.IGNORECASE)
    if hm:
        return int(hm.group(1)) * 60 + int(hm.group(2))

    # e.g. "2:30" or "2:30:00"
    colon = re.search(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b", text)
    if colon:
        return int(colon.group(1)) * 60 + int(colon.group(2))

    # e.g. "120 minutes" / "120 min"
    mins = re.search(r"(\d+)\s*min(?:utes?)?", text, re.IGNORECASE)
    if mins:
        return int(mins.group(1))

    # e.g. "2 hours"
    hours = re.search(r"(\d+)\s*hours?", text, re.IGNORECASE)
    if hours:
        return int(hours.group(1)) * 60

    return 0


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class FaneditScraper:
    """Implements find_movie, get_details, and nfo_url for fanedit.org."""

    def __init__(self, addon) -> None:
        self._addon = addon
        # Settings are read each call so that changes take effect immediately.

    # ------------------------------------------------------------------
    # Public Kodi scraper actions
    # ------------------------------------------------------------------

    def find_movie(self, handle: int, title: str, year: str = "") -> None:
        """
        Search for *title* on fanedit.org using the Google Custom Search API
        and report matching ListItems to Kodi.
        """
        api_key = self._addon.getSetting("google_api_key").strip()
        cx = self._addon.getSetting("google_cx").strip()

        if not api_key or not cx:
            _log(
                "Google API key or Custom Search Engine ID not configured. "
                "Please set them in the addon settings.",
                _LOG_ERROR,
            )
            xbmcgui.Dialog().notification(
                heading="Fanedit.org Scraper",
                message="Google API key or Search Engine ID not set. Check addon settings.",
                icon=xbmcgui.NOTIFICATION_ERROR,
                time=5000,
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        query = f"site:fanedit.org {title}"
        if year:
            query += f" {year}"

        try:
            max_results = int(self._addon.getSetting("max_results") or "10")
        except ValueError:
            max_results = 10
        max_results = max(1, min(max_results, 10))  # Google CSE allows 1–10 per request

        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": max_results,
        }

        request_url = f"{GOOGLE_SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"
        _log(f"Searching: {query!r}")

        try:
            req = urllib.request.Request(request_url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_detail = ""
            try:
                raw_body = exc.read().decode("utf-8", errors="replace")
                err_json = json.loads(raw_body)
                body_detail = err_json.get("error", {}).get("message", "")
                if body_detail:
                    _log(f"Google API error body: {body_detail}", _LOG_ERROR)
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                pass
            msg = f"Google API error {exc.code}: {exc.reason}"
            _log(msg, _LOG_ERROR)
            xbmcgui.Dialog().notification(
                heading="Fanedit.org Scraper",
                message=msg,
                icon=xbmcgui.NOTIFICATION_ERROR,
                time=5000,
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
        except urllib.error.URLError as exc:
            msg = f"Google API connection failed: {exc.reason}"
            _log(msg, _LOG_ERROR)
            xbmcgui.Dialog().notification(
                heading="Fanedit.org Scraper",
                message=msg,
                icon=xbmcgui.NOTIFICATION_ERROR,
                time=5000,
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        results = []
        for item in data.get("items", []):
            link = item.get("link", "")
            item_title = _clean_html(item.get("title", ""))
            snippet = item.get("snippet", "")

            if not self._is_fanedit_detail_page(link):
                continue

            result_year = _extract_year(snippet) or _extract_year(item_title) or year

            # Google sometimes returns the title as "Name | FanEdit.org" – strip the suffix.
            item_title = re.sub(r"\s*[|\-–]\s*(?:fanedit\.org|fan\s*edit\.org).*$",
                                "", item_title, flags=re.IGNORECASE).strip()

            thumbnail = ""
            pagemap = item.get("pagemap", {})
            cse_images = pagemap.get("cse_image", [])
            if cse_images:
                thumbnail = cse_images[0].get("src", "")

            list_item = xbmcgui.ListItem(item_title, offscreen=True)
            tag = list_item.getVideoInfoTag()
            tag.setTitle(item_title)
            if result_year:
                tag.setYear(int(result_year))
            tag.setPlot(snippet)
            if thumbnail:
                list_item.setArt({"thumb": thumbnail})

            results.append((link, list_item, True))

        _log(f"Search returned {len(results)} usable result(s)")
        xbmcplugin.addDirectoryItems(handle, results)
        xbmcplugin.endOfDirectory(handle, succeeded=True)

    def get_details(self, handle: int, url: str) -> None:
        """
        Fetch the fanedit.org page at *url*, parse its metadata, and return a
        fully populated ListItem to Kodi.
        """
        if not url:
            _log("get_details called with no URL", _LOG_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        _log(f"Fetching details from: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            _log(f"Failed to fetch {url}: {exc}", _LOG_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        details = self._parse_fanedit_page(html, url)
        _log(f"Parsed details: title={details.get('title')!r}, year={details.get('year')}")

        list_item = xbmcgui.ListItem(details.get("title", ""), offscreen=True)
        tag = list_item.getVideoInfoTag()

        if details.get("title"):
            tag.setTitle(details["title"])
        if details.get("original_title"):
            tag.setOriginalTitle(details["original_title"])
        if details.get("plot"):
            tag.setPlot(details["plot"])
        if details.get("fanedit_type"):
            tag.setTagLine(details["fanedit_type"])
        if details.get("year"):
            tag.setYear(details["year"])
        if details.get("runtime"):
            # Kodi expects runtime in seconds for InfoTagVideo
            tag.setDuration(details["runtime"] * 60)
        if details.get("editor"):
            tag.setDirectors([details["editor"]])
            tag.setWriters([details["editor"]])
        if details.get("genres"):
            tag.setGenres(details["genres"])
        if details.get("rating"):
            tag.setRating(details["rating"], details.get("votes", 0), defaultt=True)
        if details.get("fanedit_id"):
            tag.setUniqueID(details["fanedit_id"], "fanedit")

        art = {}
        if details.get("poster"):
            art["thumb"] = details["poster"]
            art["poster"] = details["poster"]
        if details.get("fanart"):
            art["fanart"] = details["fanart"]
        if art:
            list_item.setArt(art)

        xbmcplugin.setResolvedUrl(handle, True, list_item)

    def get_artwork(self, handle: int, fanedit_id: str) -> None:
        """
        Fetch available artwork for the fanedit identified by *fanedit_id*
        (the URL slug stored as the default unique ID by ``get_details``).
        """
        if not fanedit_id:
            _log("get_artwork called with no ID", _LOG_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        url = f"{FANEDIT_BASE_URL}/{fanedit_id}/"
        _log(f"Fetching artwork from: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            _log(f"Failed to fetch artwork for {fanedit_id!r}: {exc}", _LOG_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        details = self._parse_fanedit_page(html, url)

        list_item = xbmcgui.ListItem(details.get("title", ""), offscreen=True)
        tags = list_item.getVideoInfoTag()

        poster = details.get("poster", "")
        if poster:
            tags.addAvailableArtwork(poster, "poster")

        fanart_list = []
        if details.get("fanart"):
            fanart_list.append({"image": details["fanart"], "preview": details["fanart"]})
        elif poster:
            # Fall back to poster when no dedicated fanart image is available
            fanart_list.append({"image": poster, "preview": poster})
        if fanart_list:
            list_item.setAvailableFanart(fanart_list)

        xbmcplugin.setResolvedUrl(handle, True, list_item)

    def nfo_url(self, handle: int, nfo: str) -> None:
        """
        Extract a fanedit.org URL from raw NFO text so Kodi can call
        get_details automatically when an NFO file is present.
        """
        match = re.search(
            r"https?://(?:www\.)?fanedit\.org/[^\s<>\"']+",
            nfo,
        )
        if match:
            url = match.group(0).rstrip("/")
            _log(f"NFO URL found: {url}")
            list_item = xbmcgui.ListItem(url, offscreen=True)
            xbmcplugin.addDirectoryItem(handle, url, list_item, True)
        else:
            _log("No fanedit.org URL found in NFO content")

        xbmcplugin.endOfDirectory(handle, succeeded=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_fanedit_detail_page(url: str) -> bool:
        """
        Return True when *url* looks like a fanedit detail page rather than
        a category, tag, or search results page.

        Fanedit.org URLs for individual edits follow patterns such as:
          https://www.fanedit.org/mr-white/
          https://www.fanedit.org/fanedits/mr-white/
        Category/tag pages contain segments like /category/, /tag/, /page/.
        """
        if not re.search(r"fanedit\.org", url, re.IGNORECASE):
            return False
        # Exclude non-detail pages
        excluded = r"/(?:category|tag|page|author|search|wp-|feed|#|contact|about|forum)"
        if re.search(excluded, url, re.IGNORECASE):
            return False
        # Must have at least one path segment after the domain
        path_match = re.search(r"fanedit\.org/([^/?#]+)", url, re.IGNORECASE)
        return bool(path_match and path_match.group(1))

    @staticmethod
    def _parse_fanedit_page(html: str, url: str) -> dict:
        """
        Parse a fanedit.org page and return a dict with the following keys
        (all optional / may be missing):

          title, original_title, plot, year, runtime, editor,
          genres, fanedit_type, rating, votes, poster, fanedit_id

        fanedit.org is a WordPress site running the JReviews plugin.  All
        fanedit-specific metadata is stored in custom-field ``<div>`` elements
        whose outermost container carries a pair of CSS classes:
          - a unique field class   (e.g. ``jrFaneditorname``)
          - the generic row class  (``jrFieldRow``)

        The actual value lives in a child ``<div class="jrFieldValue">``.
        Rating data is available as Schema.org ``aggregateRating`` microdata.
        """
        details: dict = {}

        # ----------------------------------------------------------------
        # Internal helpers
        # ----------------------------------------------------------------

        def _field_value_block(class_name: str) -> str:
            """
            Return the raw inner HTML of the ``jrFieldValue`` div for the
            JReviews field whose outer div contains *class_name*.
            Returns an empty string when not found.
            """
            pattern = (
                r'<div[^>]+class="[^"]*'
                + re.escape(class_name)
                + r'[^"]*"[^>]*>'
                r".*?<div[^>]+class=\"jrFieldValue\"[^>]*>(.*?)</div>"
            )
            m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            return m.group(1) if m else ""

        def _field_text(class_name: str) -> str:
            """Return plain-text content of a JReviews field."""
            return _clean_html(_field_value_block(class_name))

        def _field_links(class_name: str) -> list:
            """
            Return a list of link-text strings from a JReviews field.
            Falls back to plain text when no ``<a>`` tags are present.
            """
            block = _field_value_block(class_name)
            if not block:
                return []
            links = re.findall(r"<a[^>]+>([^<]+)</a>", block, re.IGNORECASE)
            if links:
                return [_clean_html(t).strip() for t in links if t.strip()]
            plain = _clean_html(block).strip()
            return [plain] if plain else []

        # ----------------------------------------------------------------
        # Unique ID from URL slug
        # ----------------------------------------------------------------
        slug_match = re.search(r"fanedit\.org/(?:[^/]+/)?([^/?#]+)/?$", url, re.IGNORECASE)
        details["fanedit_id"] = slug_match.group(1) if slug_match else ""

        # ----------------------------------------------------------------
        # Title
        # Primary:  <h1 class="contentheading"><span itemprop="headline">…</span></h1>
        # Fallback: <title> tag with " - Fanedit.org" stripped
        # ----------------------------------------------------------------
        title_match = re.search(
            r'<h1[^>]+class="[^"]*contentheading[^"]*"[^>]*>'
            r'.*?<span[^>]+itemprop=["\']headline["\'][^>]*>(.*?)</span>',
            html, re.IGNORECASE | re.DOTALL,
        )
        if title_match:
            details["title"] = _clean_html(title_match.group(1))
        else:
            title_tag = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if title_tag:
                raw = _clean_html(title_tag.group(1))
                raw = re.sub(
                    r"\s*[-–|]\s*(?:fanedit\.org|fan\s*edit\.org).*$",
                    "", raw, flags=re.IGNORECASE,
                ).strip()
                if raw:
                    details["title"] = raw

        # ----------------------------------------------------------------
        # Poster image
        # Primary:  <meta itemprop="image" content="…">
        # Fallback: fancybox href → jrMediaPhoto img src
        # ----------------------------------------------------------------
        poster_match = re.search(
            r'<meta[^>]+itemprop=["\']image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if poster_match:
            details["poster"] = poster_match.group(1).strip()
        else:
            fancybox = re.search(
                r'<a[^>]+href=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\'][^>]+class=["\'][^"\']*fancybox[^"\']*["\']',
                html, re.IGNORECASE,
            )
            if fancybox:
                details["poster"] = fancybox.group(1).strip()
            else:
                img = re.search(
                    r'<img[^>]+class=["\'][^"\']*jrMediaPhoto[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
                    html, re.IGNORECASE,
                )
                if img:
                    details["poster"] = img.group(1).strip()

        # ----------------------------------------------------------------
        # JReviews custom fields
        # ----------------------------------------------------------------

        # Faneditor (director / editor credit)
        editor_links = _field_links("jrFaneditorname")
        if editor_links:
            details["editor"] = editor_links[0]

        # Original movie / show title
        orig_links = _field_links("jrOriginalmovietitle")
        if orig_links:
            details["original_title"] = orig_links[0]

        # Genre(s) – keep all values
        genre_links = _field_links("jrGenre")
        if genre_links:
            details["genres"] = genre_links

        # Fanedit type (e.g. TV-to-Movie, FanFix, Extended Edition…)
        fanedit_type_links = _field_links("jrFanedittype")
        fanedit_type = fanedit_type_links[0] if fanedit_type_links else _field_text("jrFanedittype")
        if fanedit_type:
            details["fanedit_type"] = fanedit_type

        # Year – prefer fanedit release year, fall back to original release year
        fanedit_date_text = _field_text("jrFaneditreleasedate")
        year = _extract_year(fanedit_date_text)
        if not year:
            year = _extract_year(_field_text("jrOriginalreleasedate"))
        if year:
            details["year"] = int(year)

        # Fanedit running time (minutes)
        runtime_text = _field_text("jrFaneditrunningtimemin")
        if runtime_text:
            mins = _parse_runtime_minutes(runtime_text)
            if mins:
                details["runtime"] = mins

        # Plot: synopsis + optional intention paragraph
        synopsis = _field_text("jrBriefsynopsis")
        intention = _field_text("jrIntention")
        plot_parts = [p for p in [synopsis, intention] if p]
        if plot_parts:
            details["plot"] = "\n\n".join(plot_parts)

        # ----------------------------------------------------------------
        # Ratings – Schema.org aggregateRating microdata
        # The block starts with  itemprop="aggregateRating"  and contains
        # both itemprop="reviewCount" and itemprop="ratingValue".
        # ----------------------------------------------------------------
        agg_start = html.find('itemprop="aggregateRating"')
        if agg_start < 0:
            agg_start = html.find("itemprop='aggregateRating'")
        if agg_start >= 0:
            # Read enough HTML to capture all sub-elements of the block
            agg_block = html[agg_start: agg_start + 3000]
            rv = re.search(
                r'itemprop=["\']ratingValue["\'][^>]*>([\d.]+)<',
                agg_block, re.IGNORECASE,
            )
            rc = re.search(
                r'itemprop=["\']reviewCount["\'][^>]*>(\d+)<',
                agg_block, re.IGNORECASE,
            )
            if rv:
                details["rating"] = float(rv.group(1))
            if rc:
                details["votes"] = int(rc.group(1))

        # Fallback: trusted reviewer rating from jrOverallEditor block
        if "rating" not in details:
            ed_block = re.search(
                r'<div[^>]+class="[^"]*jrOverallEditor[^"]*"[^>]*>(.*?)</div>\s*</div>',
                html, re.IGNORECASE | re.DOTALL,
            )
            if ed_block:
                ed_rv = re.search(
                    r'<span[^>]+class="[^"]*jrRatingValue[^"]*"[^>]*>\s*<span>([\d.]+)</span>',
                    ed_block.group(0), re.IGNORECASE,
                )
                if ed_rv:
                    details["rating"] = float(ed_rv.group(1))

        return details
