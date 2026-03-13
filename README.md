# kodi-fanedit-scraper

A Kodi 21 (Omega) metadata scraper that looks up fan-edit movies on
[fanedit.org](https://www.fanedit.org) and imports their details (title,
plot, poster, editor, runtime, year, genres, rating) directly into your Kodi
library.

The scraper queries **fanedit.org's own native search** directly — no API key
or external service is required.

---

## Requirements

| Component | Version |
|-----------|---------|
| Kodi | 21 (Omega) or newer |
| Python | 3.x (bundled with Kodi 21) |

---

## Installation

### Manual (zip install)

1. Download or clone this repository.
2. In Kodi go to **Add-ons → Install from zip file** and select the
   repository folder (or a zip of it).
3. Kodi will install the addon as `metadata.fanedit.org`.

---

## Configuration

No API key or external account is required.

1. In Kodi go to **Add-ons → My add-ons → Information providers →
   Movies** and open **Fanedit.org Scraper**.
2. Click **Configure** (or **Settings**).
3. Optionally change **Maximum search results** (1–10, default 10).
4. Click **OK**.

---

## Usage

1. In Kodi add a movie source that contains your fan-edit video files.
2. When prompted to choose an information provider, select
   **Fanedit.org Scraper**.
3. Kodi will search for each filename; you will be shown a list of
   matching fanedit.org entries to choose from.
4. Confirm the correct entry and Kodi will import the full metadata and
   artwork automatically.

### NFO files

If you place an NFO file next to a video file containing a fanedit.org URL,
e.g.:

```xml
<movie>
  <uniqueid type="fanedit">mr-white</uniqueid>
  https://www.fanedit.org/mr-white/
</movie>
```

the scraper will detect the URL and fetch details automatically without
prompting you to search.

---

## Metadata scraped from fanedit.org

| Kodi field | fanedit.org source |
|------------|--------------------|
| Title | Page / Open Graph title |
| Original title | "Original Work" field |
| Plot | Page description / Open Graph description |
| Poster | Featured image / `og:image` |
| Year | Year found near date/release context |
| Runtime | Runtime / Running Time field |
| Director | Fan editor name |
| Writer | Fan editor name |
| Genres | WordPress tags / genre links |
| Rating | Rating/score field (normalised to /10) |

---

## Development

### Project layout

```
metadata.fanedit.org/
├── addon.xml                         # Kodi addon manifest
├── default.py                        # Entry point – routes Kodi scraper actions
├── scraper.py                        # Core search & parsing logic
├── changelog.txt
├── README.md
└── resources/
    ├── settings.xml                  # Addon settings UI definition
    └── language/
        └── English/
            └── strings.po            # Localisation strings
```

### Running the unit tests

```bash
python -m pytest tests/
```

---

## Licence

MIT – see [LICENSE](LICENSE).
