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
  -h, --help             show this help message and exit
  -d, --debugmode        Debug mode
  -m LOCALDIR, --dir LOCALDIR
                         Path to M3U directory
  -c CACHEDIR, --cache CACHEDIR
                         Path to Cache directory
  -e EPGDIR, --epg EPGDIR
                         Path to EPG directory
  -l LOGDIR, --log LOGDIR
                         Path to log directory
  -t EPGHOURS, --time EPGHOURS
                         Number of EPG Hours to collect
  -x XLONG, --longitude XLONG
                         Longitude in decimal format
  -y YLAT, --latitude YLAT
                         Latitude in decimal format
</pre>
#### --debugmode

Debug mode will ignore all directory options and create the subdirectory ./pluto_debug/ next to the script. The M3U and XML files will not be generated, but instead added straight into the log.

#### --dir, --cache, --epg, --log

Pretty self-explanatory — Where you want the individual files to go. The default directory is next to the script. Filenames themselves are static and can't be changed.

#### --time option

As it is now, Pluto only delivers a maximum of about 9-10 hours of EPG. The script defaults to 8. If you need more you can push it, but this setting was added more to limit EPG.

#### --longitude, --latitude

Pluto.tv stream urls are autopopulated with your geolocation as decimal longitude and latitude. If the values are changed to zero it doesn't seem to make a difference, but I added the option to change them in case advertisements are targeted by location, or the values are one day used for the saddest, easy to bypass geoblocking ever. Format is NN.NNNN/-NN.NNNN (to four decimal points).
