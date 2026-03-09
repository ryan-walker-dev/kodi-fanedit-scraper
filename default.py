"""
Fanedit.org Kodi Metadata Scraper – entry point.

Kodi calls this script with:
  sys.argv[0]  plugin://metadata.fanedit.org/
  sys.argv[1]  handle (integer)
  sys.argv[2]  URL-encoded parameters, e.g. ?action=find&title=Mr+White&year=2019

Supported actions
-----------------
find        Search fanedit.org via Google Custom Search API and return candidate
            ListItems so the user can pick the correct fanedit.
getdetails  Fetch and parse a single fanedit.org page identified by 'url'.
nfourl      Extract a fanedit.org URL from NFO file content so Kodi can pass it
            to getdetails automatically.
"""

import sys
import urllib.parse

import xbmcaddon
import xbmcplugin

from scraper import FaneditScraper


def run() -> None:
    addon = xbmcaddon.Addon()
    handle = int(sys.argv[1])
    params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))

    action = params.get("action", "")
    scraper = FaneditScraper(addon)

    if action == "find":
        scraper.find_movie(handle, params.get("title", ""), params.get("year", ""))
    elif action == "getdetails":
        scraper.get_details(handle, params.get("url", ""))
    elif action == "nfourl":
        scraper.nfo_url(handle, params.get("nfo", ""))
    else:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


run()
