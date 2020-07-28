#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
""" A Script for setting up full TVHeadend support for Pluto.tv"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
#import uuid
import logging
import argparse
import pathlib
import re
from urllib.parse import urlencode
from datetime import datetime
from decimal import Decimal
from tzlocal import get_localzone
import wget
from furl import furl
from lxml import etree as lmntree
from wand.image import Image
from wand.color import Color

parser = argparse.ArgumentParser()
parser.add_argument('--debugmode', default=False, action='store_true', help="Debug mode")
parser.add_argument('-d', '--dir', dest='localdir', help="Path to M3U directory")
parser.add_argument('-c', '--cache', dest='cachedir', help="Path to cache directory")
parser.add_argument('-e', '--epg', dest='epgdir', help="Path to EPG directory")
parser.add_argument('-l', '--log', dest='logdir', help="Path to log directory")
parser.add_argument('-i', '--picondir', dest='picondir', help="Path to picon cache directory")
parser.add_argument('-f', '--colour', dest='hexcolour', default='transparent',
                    help="Colour in hex #1E1E1E format for image background")
parser.add_argument('-m', '--monopicon', dest='monopicon', default=False, action='store_true',
                    help="Use monochrome (all-white) picon")
parser.add_argument('-w', '--overwritepicons', dest='overwritepicons',
                    default=False, action='store_true',
                    help="Replace existing picons with newly downloaded versions")
parser.add_argument('-t', '--time', dest='epghours',
                    help="Number of EPG Hours to collect")
parser.add_argument('-x', '--longitude', dest='xlong', default=0,
                    help="Longitude in decimal format")
parser.add_argument('-y', '--latitude', dest='ylat', default=0,
                    help="Latitude in decimal format")
args = parser.parse_args()

localtimezone = get_localzone()
debugmode = args.debugmode
localdir = args.localdir
cachedir = args.cachedir
epgdir = args.epgdir
logdir = args.logdir
picondir = args.picondir
hexcolour = args.hexcolour
monopicon = args.monopicon
overwritepicons = args.overwritepicons
EPGHOURS = args.epghours
XLONG = str(args.xlong)
YLAT = str(args.ylat)
M3U8FILE = "plutotv.m3u8"
CACHEFILE = "plutocache.json"
EPGFILE = "plutotvepg.xml"
LOGFILE = "plutotv.log"
DEFAULTEPGHOURS = 8
MAXEPGHOURS = 10

if not localdir:
    localdir = os.path.dirname(os.path.realpath(__file__))
if not cachedir:
    cachedir = localdir
if not epgdir:
    epgdir = localdir
if not logdir:
    logdir = localdir
if not picondir.endswith("/"):
    picondir = picondir + "/"

if debugmode:
    debugdir = os.path.dirname(os.path.realpath(__file__)) + "/plutotv_debug"
    cachedir = debugdir
    localdir = debugdir
    epgdir = debugdir
    logdir = debugdir
    LEVEL = logging.DEBUG

cachepath = os.path.join(cachedir, CACHEFILE)
m3u8path = os.path.join(localdir, M3U8FILE)
epgpath = os.path.join(epgdir, EPGFILE)
logpath = os.path.join(logdir, LOGFILE)

fourplaces = Decimal(10) ** -4
XLONG = Decimal(XLONG).quantize(fourplaces)
YLAT = Decimal(YLAT).quantize(fourplaces)

def exists(ipath, create=False):
    """ Checks if a folder or file exists and optionally
        creates if missing """

    fpath, fname = os.path.split(ipath)
    try:
        os.stat(fpath)
        try:
            os.access(fpath, os.W_OK)
        except os.error:
            logging.error("Write permissions on path %s are incorrect. Exiting.", fpath)
            sys.exit()
    except os.error:
        logging.warning("Path %s doesn't exist. Creating.", fpath)
        try:
            os.mkdir(fpath)
        except os.error:
            logging.error("Can't create directory %s!", fpath)
            return False
    if fname:
        if not fname.endswith('logoPNG.png'):
            if debugmode:
                if pathlib.Path.exists(ipath):
                    debugipath = ipath + " exists."
                    logging.debug(debugipath)
            else:
                debugipath = ipath + " doesn't exist. It will be created."
                logging.debug(debugipath)
                return True

            if create:
                fileexists = "File " + ipath + " doesn't yet exist. Creating."
                logging.info(fileexists)
                try:
                    temp = open(ipath, "w")
                    temp.close()
                    return True
                except IOError:
                    logging.error("Can't create file %s!", fpath)
                    sys.exit()
    return True

exists(cachedir, True)
exists(epgdir, True)
exists(logdir, True)
exists(picondir, True)

LEVEL = logging.INFO
handlers = [logging.FileHandler(logpath, 'w'), logging.StreamHandler()]
logging.basicConfig(level=LEVEL, format='[%(levelname)s]: %(message)s', handlers=handlers)

if debugmode:
    XYUSED = "Longitude used: " + str(XLONG) + ", Latitude used: " + str(YLAT)
    logging.debug(XYUSED)

if EPGHOURS:
    # check for --hours argument
    if not EPGHOURS.isdigit():
        logging.error("Hours argument must be an integer.")
        sys.exit()
    if int(EPGHOURS) > MAXEPGHOURS:
        HOURSWARN = ("Hours argument cannot be longer than " + \
                    str(MAXEPGHOURS) + ". Using max value.")
        logging.warning(HOURSWARN)
        EPGHOURS = MAXEPGHOURS
else:
    EPGHOURS = DEFAULTEPGHOURS
    HOURSWARN = "Fetching default EPG of " + str(DEFAULTEPGHOURS) + " hours."
    logging.warning(HOURSWARN)

if debugmode:
    HOURSUSED = 'Episode Hours supplied: ' + str(EPGHOURS)
    logging.debug(HOURSUSED)

if debugmode:
    if not os.path.isdir(debugdir):
        os.mkdir(debugdir)
    debugcachepath = "Cache Path: " + debugdir + "/" + CACHEFILE
    logging.debug(debugcachepath)
    debugm3u8path = "M3u8 Path: " + debugdir + "/" + M3U8FILE
    logging.debug(debugm3u8path)
    debugepgpath = "EPG Path: " + debugdir + "/" + epgpath
    logging.debug(debugepgpath)
    debuglogpath = 'Log Path: ' + debugdir + "/"
    logging.debug(debuglogpath)

def piconget(pid, mnpicon, picndir, piconslug, hxclr):
    """ Function for fetching and manipulating picons """

    if exists(picndir):
        urlbase = "http://images.pluto.tv/channels/"
        if mnpicon:
            urlend = 'solidLogoPNG.png'
        else:
            urlend = 'colorLogoPNG.png'

        geturl = urlbase + "/" + pid + "/" + urlend
        savename = picndir + piconslug + ".png"

        if not exists(savename) or overwritepicons:
            _f = urllib.request.urlopen(geturl)
            with Image(file=_f) as img:
                result = re.match("^(?:#)?[0-9a-fA-F]{3,6}$", str(hxclr))
                if result:
                    if not hxclr.startswith("#"):
                        hxclr = "#" + hxclr
                    img.background_color = Color(hxclr)
                elif hxclr == "transparent":
                    img.background_color = Color('transparent')
                else:
                    logging.error("Background colour option must follow '#FFFFFF' hex format")
                    sys.exit()
                img.extent(width=576, height=576, x=0, y=-144)
                img.save(filename=savename)
            _f.close()
    else:
        try:
            os.mkdir(picndir)
        except os.error:
            print("Could not create " + picndir)

def newcache(cchepath):
    """ Checks how old the cache is """

    try:
        os.path.isfile(cchepath)
    # it's under 30 mins old and not an empty file
        now = time.time()
        mtime = os.path.getmtime(cchepath)
        if now - mtime <= 1800:
            return False
        return True
    except IOError:
        logging.error("There was an issue fetching the cache.")
        sys.exit()


def getnewdata():
    """ Gets new json cache """
    try:
        os.remove(cachepath)
    except os.error:
        pass
    tdelta = int(EPGHOURS)*60*60
    now = time.time()
    later = now + tdelta
    # 2020-03-24%2021%3A00%3A00.000%2B0000
    starttime = urllib.parse.quote(datetime.fromtimestamp(now).
                                   strftime('%Y-%m-%d %H:00:00.000+0000'))
    # 2020-03-25%2005%3A00%3A00.000%2B0000
    stoptime = urllib.parse.quote(datetime.fromtimestamp(later).
                                  strftime('%Y-%m-%d %H:00:00.000+0000'))
    url = "http://api.pluto.tv/v2/channels?start=" + starttime + "&stop=" + stoptime

    if debugmode:
        logging.debug(url)

    logging.debug("Using api.pluto.tv, writing %s.", CACHEFILE)

    try:
        wget.download(url, out=cachepath)
    except IOError:
        logging.error("There was an issue downloading EPG data. Exiting.")
        sys.exit()

def datetime_from_utc_to_local(utc_datetime):
    """ changes datetime from utc to computer's local time """
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

def main():
    """ the big show """
    logging.info('Grabbing EPG...')

    if not newcache(cachepath):
        logging.info("Using %s, it's under 30 minutes old.", cachepath)
    else:
        getnewdata()

    with open(cachepath) as _f:
        data = json.load(_f)
        if not debugmode:
            m3ufile = open(m3u8path, 'w')
            m3ufile.write("#EXTM3U\n")
        else:
            debugm3u = "#EXTM3U\n"

        xml = lmntree.Element('tv', \
        attrib={"generator-info-name":"Zang's Pluto.TV TVHeadend generator",\
                "generator-info-url":"https://github.com/zang74/PlutoIPTV"})

        badchannels = ["Announcement", "Privacy Policy"]

        for channel in data:

            # M3U8 Playlist

            if channel['isStitched']:
                if not channel['name'] in badchannels:
                    deviceid = channel['_id']
                    chnumber = str(channel['number'])
                    # deviceid = uuid.uuid1()
                    # sid = uuid.uuid4()
                    sid = chnumber
                    baseurl = (furl(channel['stitched']['urls'][0]['url']).
                               remove(args=True, fragment=True).url)
                    if not str(XLONG) and not str(YLAT):
                        _l = furl(channel['stitched']['urls'][0]['url'])
                        xnewlong = _l.args['deviceLat']
                        ynewlat = _l.args['deviceLon']
                    else:
                        xnewlong = str(XLONG)
                        ynewlat = str(YLAT)

                    mydict = {
                        'advertisingId': '',
                        'appName': 'web',
                        'appVersion': 'DNT',
                        'appStoreUrl': '',
                        'architecture': '',
                        'buildVersion': '',
                        'clientTime': '0',
                        'deviceDNT': '0',
                        'deviceId': deviceid,
                        'deviceLat': ynewlat,
                        'deviceLon': xnewlong,
                        'deviceMake': 'Chrome',
                        'deviceModel': 'web',
                        'deviceType': 'web',
                        'deviceVersion': 'DNT',
                        'includeExtendedEvents': 'false',
                        'sid': sid,
                        'userId': '',
                        'serverSideAds': 'true',
                        'terminate': 'false',
                        'marketingRegion': 'US'
                    }
                    m3uurl = baseurl + "?" + urlencode(mydict)
                    slug = channel['slug']
                    if monopicon:
                        logo = channel['solidLogoPNG']['path']
                    else:
                        logo = channel['colorLogoPNG']['path']
                    group = channel['category']
                    chname = channel['name']

                    ## image routine
                    if picondir:
                        piconslug = slug + ".plutotv"
                        logo = picondir + piconslug + ".png"
                        piconget(deviceid, monopicon, picondir, piconslug, hexcolour)

                    m3uoutput = ("\n#EXTINF:-1 tvg-name=\"" + chname + "\" tvg-id=\"" +
                                 deviceid + ".plutotv\" " + "tvg-logo=\"" + logo +
                                 "\" group-title=\"" + group + "\"," + chname + "\n" +
                                 m3uurl + "\n")

                    logging.info('Adding %s channel.', chname)

                    if not debugmode:
                        m3ufile.write(m3uoutput)
                    else:
                        debugm3u += m3uoutput
                else:
                    logging.info("Skipping 'fake' channel %s.", channel['name'])

                # XMLTV EPG

                tvgidslug = channel['_id'] + ".plutotv"
                xmlchannel = lmntree.SubElement(xml, "channel", id=tvgidslug)
                lmntree.SubElement(xmlchannel, "display-name").text = channel['name']

                if picondir:
                    xmlicon = picondir + piconslug + ".png"
                elif monopicon:
                    xmlicon = channel['solidLogoPNG']['path']
                else:
                    xmlicon = channel['colorLogoPNG']['path']

                lmntree.SubElement(xmlchannel, "icon", src=xmlicon)

                for episodes in channel['timelines']:

                    categorylist = []
                    epdescription = episodes['episode']['description']
                    epdescription = epdescription.replace('\x92', '')
                    if episodes['episode']['genre']:
                        categorylist.append(episodes['episode']['genre'])
                    if episodes['episode']['subGenre']:
                        categorylist.append(episodes['episode']['subGenre'])
                    if episodes['episode']['series']['type'] == "film":
                        categorylist.append("movie")
                    elif episodes['episode']['series']['type'] == "live":
                        categorylist.append('news')
                    else:
                        categorylist.append('series')
                    eppremiere = episodes['episode']['firstAired']
                    tpremiere = datetime.fromisoformat(eppremiere[:-1])
                    epdate = tpremiere.strftime("%Y%m%d")
                    epshow = episodes['episode']['name']
                    eprating = episodes['episode']['rating']
                    eptitle = episodes['title']
                    duration = episodes['episode']['duration']
                    epstart = episodes['start']
                    epstop = episodes['stop']
                    epnumber = episodes['episode']['number']
                    # epicon = episodes['episode']['number']
                    starttime = datetime.fromisoformat(epstart[:-1])
                    tstart = localtimezone.localize(starttime)
                    localstart = tstart.strftime("%Y%m%d%H%M%S %z")
                    stoptime = datetime.fromisoformat(epstop[:-1])
                    tstop = localtimezone.localize(stoptime)
                    localstop = tstop.strftime("%Y%m%d%H%M%S %z")
                    # idslug = channel['slug'] + ".plutotv"
                    if channel['category'] == "Latino":
                        eplang = "es"
                    else:
                        eplang = "en"

                    logging.info('Adding instance of %s to channel %s.',
                                 eptitle, channel['name'])

                    eptime = duration / 1000 / 60

                    xmlepisode = lmntree.SubElement(
                        xml, "programme", start=localstart, stop=localstop, channel=tvgidslug
                        )
                    lmntree.SubElement(xmlepisode, "title", lang=eplang).text = epshow
                    if eptitle:
                        lmntree.SubElement(xmlepisode, "sub-title", lang=eplang).text = eptitle
                    lmntree.SubElement(xmlepisode, "desc", lang=eplang).text = epdescription
                    # xmlcredits = lmntree.SubElement(xmlepisode, "credits")
                    lmntree.SubElement(xmlepisode, "date").text = epdate
                    for cat in categorylist:
                        lmntree.SubElement(xmlepisode, "category", lang=eplang).text = cat
                    lmntree.SubElement(xmlepisode, "length", units='minutes').text = str(eptime)
                    lmntree.SubElement(xmlepisode, "episode-num",
                                       system='onscreen').text = str(epnumber)
                    xmlrating = lmntree.SubElement(xmlepisode, "rating", system='US')
                    lmntree.SubElement(xmlrating, "value").text = eprating


        if not debugmode:
            m3ufile.close()
        else:
            logging.debug(" ")
            logging.debug("================")
            logging.debug("== M3U OUTPUT ==")
            logging.debug("================")
            logging.debug(" ")
            for m3uline in debugm3u.splitlines():
                logging.debug(m3uline)
            logging.debug(" ")
            logging.debug("====================")
            logging.debug("== END M3U OUTPUT ==")
            logging.debug("====================")
            logging.debug(" ")


        logging.info("Success! Wrote the M3U8 tuner to %s!", m3u8path)
        xmltvtree = lmntree.ElementTree(xml)
        root = xmltvtree.getroot()

        # sort the first layer
        root[:] = sorted(root, key=lambda child: (child.tag, child.get('id'), child.get('channel')))
        xmldata = lmntree.tostring(root, pretty_print=True, encoding="utf-8",
                                   xml_declaration=True,
                                   doctype='<!DOCTYPE tv SYSTEM "xmltv.dtd">')
        if not debugmode:
            with open(epgpath, "wb") as _f:
                _f.write(xmldata)
                _f.close()
                logging.info("Success! Wrote the EPG to %s!", m3u8path)
        else:
            logging.debug(" ")
            logging.debug("================")
            logging.debug("== M3U OUTPUT ==")
            logging.debug("================")
            logging.debug(" ")
            for xmlline in xmldata.splitlines():
                logging.debug(xmlline.decode())
            logging.debug(" ")
            logging.debug("====================")
            logging.debug("== END XML OUTPUT ==")
            logging.debug("====================")
            logging.debug(" ")

            logging.debug("Success! Simulated write of EPG!")

if __name__ == "__main__":
    main()
