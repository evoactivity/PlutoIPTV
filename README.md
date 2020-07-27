# PlutoIPTV for TVHeadend in Python

Grab EPG &amp; M3U from Pluto.tv

Based on the work of https://github.com/TylerB260/PlutoXML and https://github.com/evoactivity/PlutoIPTV

### Usage

```bash
$ pluto.py $ARGS
```
With no arguments, the following files will be created in the same directory as the script:

- plutotvepg.xml (EPG)
- plutotv.m3u8 (M3U8 Playlist)
- plutocache.json (raw JSON cache file)
- plutotv.log (Log file)

### Optional Script Arguments
<pre>
  -h, --help            show this help message and exit
  --debugmode           Debug mode
  -d LOCALDIR, --dir LOCALDIR
                        Path to M3U directory
  -c CACHEDIR, --cache CACHEDIR
                        Path to cache directory
  -e EPGDIR, --epg EPGDIR
                        Path to EPG directory
  -l LOGDIR, --log LOGDIR
                        Path to log directory
  -i PICONDIR, --picondir PICONDIR
                        Path to picon cache directory
  -f HEXCOLOUR, --colour HEXCOLOUR
                        Colour in hex #1E1E1E format for image background
  -m, --monopicon       Use monochrome (all-white) picon
  -w, --overwritepicons
                        Replace existing picons with newly downloaded versions
  -t EPGHOURS, --time EPGHOURS
                        Number of EPG Hours to collect
  -x XLONG, --longitude XLONG
                        Longitude in decimal format
  -y YLAT, --latitude YLAT
                        Latitude in decimal format
</pre>
#### --debugmode (optional)

Debug mode will ignore all directory options and create the subdirectory ./pluto_debug/ next to the script. The M3U and XML files will not be generated, but instead added straight into the log. The log and cache files will be saved into ./pluto_debug/.

#### --dir, --cache, --epg, --log (optional)

Pretty self-explanatory — Where you want the individual files to go. The default directory is next to the script. Filenames themselves are static and can't be changed.

#### --picondir (optional)

A location to store channel logos as "picons". Logo images will be pulled from the pluto.tv site, expanded into a square picon (no cropping takes place, only expansion of the canvas), and saved with a channel-identifiable filename in the directory submitted.

#### --colour (optional)

A hexidecimal RGB value (#1F1F1F) to use as a background colour to flatten transparent pngs.

#### --monopicon (optional)

Download white logo on transparency instead of default colour logo on transparency. Can be combined with --colour

#### -- overwritepicons (optional)

By default, if the picondir option is selected, the script will only download those icons it cannot find in the given directory. This dramatically speeds up the script and saves needless downloads. This option forces an overwrite of those picon files. Can be useful if icons/channels change or as an once-a-week option. 

#### --time (optional)

As it is now, Pluto only delivers a maximum of about 9-10 hours of EPG. The script defaults to 8. If you need more you can push it, but this setting was added more to limit EPG.

#### --longitude, --latitude (optional)

Pluto.tv stream urls are autopopulated with your geolocation as decimal longitude and latitude. If the values are changed to zero it doesn't seem to make a difference, but I added the option to change them in case advertisements are targeted by location, or the values are one day used for the saddest, easy to bypass geoblocking ever. Format is NN.NNNN/-NN.NNNN (to four decimal points).
