# PlutoIPTV

Grab EPG &amp; M3U from Pluto.tv

Based on https://github.com/TylerB260/PlutoXML

## Usage

### Run

```bash
$ npx pluto-iptv
```

This will create an `epg.xml` file and a `playlist.m3u` file

#### Filtering for favorites
If you don't want all channels from pluto, you can create a "favorites" file: `pluto-favorites`.  In this file, one per line, you can list "slugs" of channels and only those channels will be downloaded.  You can add comments by starting the line with `#`.

Example:
```text
# Nostalgia
80s-rewind
90s-throwback
after-school-cartoons

# Music
vevo-80s
vevo-90s
vevo-pop

# News
black-news-channel
cbsn-2
nbc-news-now
pluto-tv-news
```
