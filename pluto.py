#!/usr/bin/env python3.7
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
from wand.api import library

parser = argparse.ArgumentParser()
parser.add_argument('--debugmode', default=False, action='store_true', help="Debug mode")
parser.add_argument('-d', '--dir', dest='localdir', help="Path to M3U directory")
parser.add_argument('-c', '--cache', dest='cachedir', help="Path to cache directory")
parser.add_argument('-e', '--epg', dest='epgdir', help="Path to EPG directory")
parser.add_argument('-l', '--log', dest='logdir', help="Path to log directory")
parser.add_argument('-i', '--picondir', dest='picondir', help="Path to picon cache directory")
parser.add_argument('-f', '--bgcolour1', dest='hexcolour1', default=None,
                    help="Colour #1 in hex #1E1E1E format for image background")
parser.add_argument('-g', '--bgcolour2', dest='hexcolour2', default=None,
                    help="Colour #2 in hex #1E1E1E format for image background")
parser.add_argument('-a', '--angle', dest='angle', default=None,
                    help="Angle for image background gradient in degrees, " +
                    " eg; '270'")
parser.add_argument('-m', '--monopicon', dest='monopicon', default=False,
                    action='store_true', help="Use monochrome (all-white) picon")
parser.add_argument('-z', '--colourful', dest='colourful',
                    default=False, action='store_true',
                    help="Solid white icon over auto-generated dark gradient backgrounds")
parser.add_argument('-b', '--bright', dest='bright',
                    default=False, action='store_true',
                    help="Does the same as --colourful, but makes the " +
                    "background gradient two-coloue and ultra-intense.")
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
HEXCOLOUR1 = args.hexcolour1
HEXCOLOUR2 = args.hexcolour2
angle = args.angle
monopicon = args.monopicon
overwritepicons = args.overwritepicons
COLOURFUL = args.colourful
CBRIGHT = args.bright
EPGHOURS = args.epghours
XLONG = str(args.xlong)
YLAT = str(args.ylat)
M3U8FILE = "plutotv.m3u8"
CACHEFILE = "plutocache.json"
EPGFILE = "plutotvepg.xml"
LOGFILE = "plutotv.log"
DEFAULTEPGHOURS = 8
MAXEPGHOURS = 10

if HEXCOLOUR1 is not None:
    result1 = re.match("^(?:#)?[0-9a-fA-F]{3,6}$", str(HEXCOLOUR1))
    if not result1:
        logging.error("Background Colour #1 must match '#FFFFFF' hex format")
        sys.exit()
    if not HEXCOLOUR1.startswith("#"):
        HEXCOLOUR1 = "#" + str(HEXCOLOUR1)

if HEXCOLOUR2 is not None:
    result2 = re.match("^(?:#)?[0-9a-fA-F]{3,6}$", str(HEXCOLOUR2))
    if not result2:
        logging.error("Background Colour #2 must match '#FFFFFF' hex format")
        sys.exit()
    if not HEXCOLOUR2.startswith("#"):
        HEXCOLOUR2 = "#" + str(HEXCOLOUR2)

if angle:
    result1 = re.match("^[0-9]{1,3}$", str(angle))
    if not result1:
        logging.error("Angle must be a only a number between 0-360")
        sys.exit()
    if not HEXCOLOUR1 and not COLOURFUL and not CBRIGHT:
        print('Angle does nothing if the arguments create a transparent background')

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
    LEVEL = logging.debug

cachepath = os.path.join(cachedir, CACHEFILE)
m3u8path = os.path.join(localdir, M3U8FILE)
epgpath = os.path.join(epgdir, EPGFILE)
logpath = os.path.join(logdir, LOGFILE)

fourplaces = Decimal(10) ** -4
XLONG = Decimal(XLONG).quantize(fourplaces)
YLAT = Decimal(YLAT).quantize(fourplaces)

def direxists(ipath):
    """ Checks if a directory exists and creates if missing """
    if not ipath.endswith("/"):
        ipath = ipath + "/"
    if not os.path.exists(ipath):
        try:
            os.mkdir(ipath)
        except os.error:
            logging.error("Can't create directory %s!", ipath)
    else:
        if not os.access(os.path.dirname(ipath), os.W_OK):
            logging.error("Can't write to directory %s! Check permissions.", ipath)
            return False
    return True

def fileexists(cpath, create=True):
    """ Checks if a file exists and creates if missing """
    dpath = os.path.dirname(cpath)
    if not os.path.isfile(cpath):
        if direxists(dpath) and create:
            try:
                pathlib.Path(cpath).touch()
            except os.error:
                logging.error("Can't create file %s!", cpath)
                return False
    return True

LEVEL = logging.INFO
handlers = [logging.FileHandler(logpath, 'w'), logging.StreamHandler()]
logging.basicConfig(level=LEVEL, format='[%(levelname)s]: %(message)s', handlers=handlers)

direxists(cachedir)
direxists(epgdir)
direxists(logdir)
direxists(picondir)


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

def tvhcategory(xtype, category, subgenre):
    ''' Creates category list using an XMLTV and TVH friendly category dictionary. '''
    xtype = xtype.strip()
    category = category.strip()
    subgenre = subgenre.strip()

    catlist = []

    if category == 'News + Opinion':
        catlist.append('News')
    elif category == 'Film':
        catlist.append('Movie')
    elif category == 'TV':
        catlist.append('Series')
        catlist.append('TVShow')
    elif category == 'Music':
        catlist.append('Music')
    elif category in ['Life + Style', 'Explore', 'Entertainment']:
        if xtype == 'film':
            catlist.append('Movie')
        else:
            catlist.append('Series')
    else:
        catlist.append('Series')

    if subgenre == 'Hobbies & Games':
        if category == 'Tech & Geek':
            catlist.append('Gaming')
            catlist.append('Technology')
            catlist.append('Computers')
        else:
            catlist.append('Game Show / Quiz / Contest')
            catlist.append('Game Show')

    moviedict = {
        'Action Classics': 'Movie / Drama',
        'Action Sci-Fi & Fantasy': 'Science Fiction / Fantasy / Horror',
        'Action Thrillers': 'Detective / Thriller',
        'Adventures': 'Adventure / Western / War',
        'African-American Action': 'Movie / Drama',
        'African-American Comedies': 'Comedy',
        'African-American Romance': 'Romance',
        'Ages 2-4': 'Movie / Drama',
        'Alien Sci-Fi': 'Science Fiction / Fantasy / Horror',
        'Animal Tales': 'Soap / Melodrama / Folkloric',
        'Animals': 'Soap / Melodrama / Folkloric',
        'Anime Action & Adventure': 'Adventure / Western / War',
        'Anime Horror': 'Science Fiction / Fantasy / Horror',
        'Anime Sci-Fi': 'Science Fiction / Fantasy / Horror',
        'Art & Design': 'Arts / Culture (without music)',
        'Arts': 'Arts / Culture (without music)',
        'B-Movie Horror': 'Science Fiction / Fantasy / Horror',
        'Best of British Humor': 'Comedy',
        'Biographical Documentaries': 'Documentary',
        'Blockbusters': 'Movie / Drama',
        'Career & Finance': 'Movie / Drama',
        'Cartoons': 'Movie / Drama',
        'Celebrity & Gossip': 'Movie / Drama',
        'Classic Comedies': 'Comedy',
        'Classic Dramas': 'Movie / Drama',
        'Classic Movie Musicals': 'Movie / Drama',
        'Classic Rock': 'Movie / Drama',
        'Classic Sci-Fi & Fantasy': 'Science Fiction / Fantasy / Horror',
        'Classic Stage Musicals': 'Movie / Drama',
        'Classic War Stories': 'Adventure / Western / War',
        'Classic Westerns': 'Adventure / Western / War',
        'Coming of Age': 'Movie / Drama',
        'Contemporary Movie Musicals': 'Musical / Opera',
        'Creature Features': 'Science Fiction / Fantasy / Horror',
        'Crime Action': 'Detective / Thriller',
        'Crime Documentaries': 'Documentary',
        'Crime Thrillers': 'Detective / Thriller',
        'Cult Comedies': 'Comedy',
        'Cult Horror': 'Science Fiction / Fantasy / Horror',
        'Deadly Disasters': 'Soap / Melodrama / Folkloric',
        'Erotic Thrillers': 'Adult drama / Movie',
        'Espionage Thrillers': 'Detective / Thriller',
        'Experimental': 'Experimental Film / Video',
        'Faith & Spirituality Documentaries' : 'Documentary',
        'Faith & Spirituality Feature Films': 'Serious / Classical / Religious / ' +
                                              'Historical movie / Drama',
        'Family Adventures': 'Adventure / Western / War',
        'Family Animation': 'Movie / Drama',
        'Family Classics': 'Movie / Drama',
        'Family Comedies': 'Comedy',
        'Family Dramas': 'Movie / Drama',
        'Family Sci-Fi & Fantasy': 'Science Fiction / Fantasy / Horror',
        'Fantasy': 'Science Fiction / Fantasy / Horror',
        'Fighting & Self Defense': 'Movie / Drama',
        'Foreign Action & Adventure': 'Adventure / Western / War',
        'Foreign Art House': 'Film / Cinema',
        'Foreign Classic Comedies': 'Comedy',
        'Foreign Classic Dramas': 'Movie / Drama',
        'Foreign Comedies': 'Comedy',
        'Foreign Documentaries': 'Documentary',
        'Foreign Gay & Lesbian': 'Movie / Drama',
        'Foreign Horror': 'Science Fiction / Fantasy / Horror',
        'Foreign Musicals': 'Musical / Opera',
        'Foreign Romance': 'Romance',
        'Foreign Sci-Fi & Fantasy': 'Science Fiction / Fantasy / Horror',
        'Foreign Thrillers': 'Detecive / Thriller',
        'Gay & Lesbian Dramas': 'Movie / Drama',
        'Gay': 'Romance',
        'General Indie Film & Short Films': 'Film / Cinema',
        'Heist Films': 'Detective / Thriller',
        'Historical Documentaries': 'Documentary',
        'Horror Classics': 'Science Fiction / Fantasy / Horror',
        'Indie Action': 'Film / Cinema',
        'Indie Comedies': 'Comedy',
        'Indie Documentaries': 'Documentary',
        'Indie Dramas': 'Film / Cinema',
        'Indie Romance': 'Romance',
        'Indie Suspense & Thriller': 'Film / Cinema',
        'Inspirational Biographies': 'Soap / Melodrama / Folkloric',
        'Inspirational Stories for Kids': 'Soap / Melodrama / Folkloric',
        'Inspirational Stories': 'Soap / Melodrama / Folkloric',
        'Investigative Journalism': 'Magazines / Reports / Documentary',
        'Kids\' Anime': 'Movie / Drama',
        'Kids\' Music': 'Movie / Drama',
        'Late Night Comedies': 'Comedy',
        'Latino Comedies': 'Comedy',
        'Martial Arts': 'Movie / Drama',
        'Men\'s Interest': 'Movie / Drama',
        'Military & War Action': 'Adventure / Western / War',
        'Military Documentaries': 'Documentary',
        'Miscellaneous Documentaries': 'Documentary',
        'Mobster': 'Detective / Thriller',
        'Mockumentaries': 'Comedy',
        'Monsters': 'Science Fiction / Fantasy / Horror',
        'Music Documentaries': 'Documentary',
        'Music': 'Movie / Drama',
        'Mystery': 'Detective / Thriller',
        'Pets': 'Movie / Drama',
        'Poker & Gambling': 'Movie / Drama',
        'Political Comedies': 'Comedy',
        'Political Documentaries': 'Documentary',
        'Political Thrillers': 'Detective / Thriller',
        'Politics': 'Movie / Drama',
        'Psychological Thrillers': 'Detective / Thriller',
        'Religion & Mythology Documentaries': 'Documentary',
        'Religious & Spiritual Dramas': 'Serious / Classical / Religious / ' +
                                        'Historical Movie / Drama',
        'Romance Classics': 'Romance',
        'Romance': 'Romance',
        'Romantic Comedies': 'Romance',
        'Romantic Dramas': 'Romance',
        'Satanic Stories': 'Science Fiction / Fantasy / Horror',
        'Sci-Fi Adventure': 'Science Fiction / Fantasy / Horror',
        'Sci-Fi Cult Classics': 'Science Fiction / Fantasy / Horror',
        'Sci-Fi Dramas': 'Science Fiction / Fantasy / Horror',
        'Sci-Fi Horror': 'Science Fiction / Fantasy / Horror',
        'Sci-Fi Thrillers': 'Science Fiction / Fantasy / Horror',
        'Science and Nature Documentaries': 'Documentary',
        'Science': 'Movie / Drama',
        'Screwball': 'Comedy',
        'Showbiz Comedies': 'Comedy',
        'Slapstick': 'Comedy',
        'Slashers and Serial Killers': 'Detective / Thriller',
        'Social & Cultural Documentaries': 'Documentary',
        'Spiritual Mysteries': 'Serious / Classical / Religious / Historical movie / Drama',
        'Spoofs and Satire': 'Comedy',
        'Sports Comedies': 'Comedy',
        'Sports Documentaries': 'Documentary',
        'Sports': 'Sports',
        'Stand-Up': 'Comedy',
        'Super Swashbucklers': 'Adventure / Western / War',
        'Supernatural Horror': 'Science Fiction / Fantasy / Horror',
        'Supernatural Sci-Fi': 'Science Fiction / Fantasy / Horror',
        'Supernatural Thrillers': 'Detective / Thriller',
        'Suspense': 'Detective / Thriller',
        'Teen Comedies': 'Comedy',
        'Teen Dramas': 'Movie / Drama',
        'Travel & Adventure Documentaries': 'Documentary',
        'Travel': 'Movie / drama',
        'Vampires': 'Science Fiction / Fantasy / Horror',
        'Werewolves': 'Science Fiction / Fantasy / Horror',
        'Westerns': 'Adventure / Western / War',
        'Women\'s Interest': 'Movie / Drama',
        'Zombies': 'Science Fiction / Fantasy / Horror'
    }

    tvdict = {
        'Action Classics': 'Show / Game show',
        'Action Sci-Fi & Fantasy': 'Show / Game show',
        'Action Thrillers': 'Show / Game show',
        'Adventures': 'Show / Game show',
        'African-American Action': 'Show / Game show',
        'African-American Comedies': 'Show / Game show',
        'African-American Romance': 'Show / Game show',
        'Ages 2-4': 'Children\'s / Youth Programmes',
        'Alien Sci-Fi': 'Show / Game show',
        'Animal Tales': 'Nature / Animals / Environment',
        'Animals': 'Nature / Animals / Environment',
        'Anime Action & Adventure': 'Show / Game show',
        'Anime Horror': 'Show / Game show',
        'Anime Sci-Fi': 'Show / Game show',
        'Anime Series': 'Show / Game show',
        'Art & Design': 'Arts / Culture (without music)',
        'Arts': 'Arts / Culture (without music)',
        'B-Movie Horror': 'Show / Game show',
        'Best of British Humor': 'Show / Game show',
        'Biographical Documentaries': 'Remarkable people',
        'Blockbusters': 'Show / Game show',
        'Boating & Sailing': 'Leisure Hobbies',
        'Car Culture': 'Leisure Hobbies',
        'Career & Finance': 'Social / Political issues / Economics',
        'Cartoons': 'Cartoons / Puppets',
        'Celebrity & Gossip': 'Popular culture / Traditional arts',
        'Classic Comedies': 'Show / Game show',
        'Classic Dramas': 'Show / Game show',
        'Classic Movie Musicals': 'Musical / Opera',
        'Classic Rock': 'Rock / Pop',
        'Classic Sci-Fi & Fantasy': 'Show / Game show',
        'Classic Stage Musicals': 'Performing Arts',
        'Classic War Stories': 'Show / Game show',
        'Classic Westerns': 'Show / Game show',
        'Coming of Age': 'Show / Game show',
        'Consumer Products & Software': 'Technology / Natural sciences',
        'Cooking Instruction': 'Cooking',
        'Creature Features': 'Show / Game show',
        'Crime Action': 'Show / Game show',
        'Crime Documentaries': 'Documentary',
        'Crime Thrillers': 'Show / Game show',
        'Cult Comedies': 'Show / Game show',
        'Cult Horror': 'Show / Game show',
        'Deadly Disasters': 'Show / Game show',
        'Disco': 'Rock / Pop',
        'DIY & How To': 'Handicraft',
        'Education & Guidance': 'Further Education',
        'Entertaining': 'Cooking',
        'Erotic Thrillers': 'Adult drama / Movie',
        'Espionage Thrillers': 'Show / Game show',
        'Experimental': 'Experimental Film / Video',
        'Fails & Pranks': 'Show / Game Show',
        'Faith & Spirituality Documentaries' : 'Documentary',
        'Family Adventures': 'Show / Game show',
        'Family Animation': 'Cartoons / Puppets',
        'Family Classics': 'Show / Game show',
        'Family Comedies': 'Show / Game show',
        'Family Dramas': 'Show / Game show',
        'Family Sci-Fi & Fantasy': 'Show / Game show',
        'Fantasy': 'Show / Game show',
        'Fighting & Self Defense': 'Martial Sports',
        'Fishing': 'Leisure Hobbies',
        'Food & Wine': 'Cooking',
        'Food Stories': 'Cooking',
        'Foreign Action & Adventure': 'Show / Game show',
        'Foreign Classic Comedies': 'Show / Game show',
        'Foreign Classic Dramas': 'Show / Game show',
        'Foreign Comedies': 'Show / Game show',
        'Foreign Documentaries': 'Documentary',
        'Foreign Gay & Lesbian': 'Show / Game show',
        'Foreign Horror': 'Show / Game show',
        'Foreign Musicals': 'Musical / Opera',
        'Foreign Romance': 'Show / Game show',
        'Foreign Sci-Fi & Fantasy': 'Show / Game show',
        'Foreign Thrillers': 'Detecive / Thriller',
        'Gaming': 'New media',
        'Gay & Lesbian Dramas': 'Show / Game show',
        'Gay': 'Show / Game show',
        'General News': 'News / Current Affairs',
        'Heist Films': 'Show / Game show',
        'Hip-Hop/Rap': 'Rock / Pop',
        'Historical Documentaries': 'Documentary',
        'History & Social Studies': 'Social / Political issues / Economics',
        'Home & Garden': 'Handicraft',
        'Home Improvement': 'Handicraft',
        'Horror Classics': 'Show / Game show',
        'Hunting': 'Leisure Hobbies',
        'Indie Action': 'Show / Game show',
        'Indie Comedies': 'Show / Game show',
        'Indie Documentaries': 'Show / Game show',
        'Indie Dramas': 'Show / Game show',
        'Indie Romance': 'Show / Game show',
        'Indie Suspense & Thriller': 'Show / Game show',
        'Inspirational Biographies': 'Remarkable People',
        'Inspirational Stories for Kids': 'Children\'s / Youth programs',
        'Inspirational Stories': 'Remarkable People',
        'Investigative Journalism': 'Magazines / Reports / Documentary',
        'Kids\' Anime': 'Cartoons / Puppets',
        'Kids\' Music': 'Children\'s / Youth programs',
        'Kids\' TV': 'Children\'s / Youth programs',
        'Late Night Comedies': 'Show / Game show',
        'Late Night TV': 'Show / Game show',
        'Latino Comedies': 'Show / Game show',
        'Magic & Illusion': 'Performing Arts',
        'Martial Arts': 'Martial sports',
        'Men\'s Interest': 'Show / Game show',
        'Military & War Action': 'Show / Game show',
        'Military Documentaries': 'Documentary',
        'Mindfulness & Prayer': 'Social / Spiritual Sciences',
        'Miscellaneous Documentaries': 'Documentary',
        'Mobster': 'Show / Game show',
        'Mockumentaries': 'Show / Game show',
        'Monsters': 'Show / Game show',
        'Music Documentaries': 'Documentary',
        'Music': 'Music / Ballet / Dance',
        'Must-See Concerts': 'Performing arts',
        'Mystery': 'Show / Game show',
        'Pets': 'Nature / Animals / Environment',
        'Poker & Gambling': 'Leisure hobbies',
        'Political Comedies': 'Show / Game show',
        'Political Documentaries': 'Documentary',
        'Political Thrillers': 'Show / Game show',
        'Politics': 'Social / Political issues / Economics',
        'Pop': 'Rock / Pop',
        'Prayer & Spiritual Growth': 'Social / Spiritual Sciences',
        'Psychological Thrillers': 'Show / Game show',
        'Punk Rock': 'Rock / Pop',
        'R&B/Soul': 'Rock / Pop',
        'Reggae': 'Rock / Pop',
        'Religion & Mythology Documentaries': 'Documentary',
        'Religious & Spiritual Dramas': 'Social / Spiritual Sciences',
        'Rock': 'Rock / Pop',
        'Romance Classics': 'Show / Game show',
        'Show / Game show': 'Show / Game show',
        'Romantic Comedies': 'Show / Game show',
        'Romantic Dramas': 'Show / Game show',
        'Satanic Stories': 'Show / Game show',
        'Sci-Fi Adventure': 'Show / Game show',
        'Sci-Fi Cult Classics': 'Show / Game show',
        'Sci-Fi Dramas': 'Show / Game show',
        'Sci-Fi Horror': 'Show / Game show',
        'Sci-Fi Thrillers': 'Show / Game show',
        'Science and Nature Documentaries': 'Education / Science / Factual Topics',
        'Science': 'Education / Science / Factual Topics',
        'Screwball': 'Show / Game show',
        'Showbiz Comedies': 'Show / Game show',
        'Singer-Songwriters': 'Folk / Traditional Music',
        'Sketch Comedies': 'Show / Game show',
        'Slapstick': 'Show / Game show',
        'Slashers and Serial Killers': 'Show / Game show',
        'Social & Cultural Documentaries': 'Social / Political Issues / Economics',
        'Spiritual Mysteries': 'Social / Spiritual sciences',
        'Spoofs and Satire': 'Show / Game show',
        'Sports & Sports Highlights': 'Sports magazine',
        'Sports Comedies': 'Show / Game show',
        'Sports Documentaries': 'Sports magazines',
        'Sports': 'Sports',
        'Stand-Up': 'Show / Game show',
        'Super Swashbucklers': 'Show / Game show',
        'Supernatural Horror': 'Show / Game show',
        'Supernatural Sci-Fi': 'Show / Game show',
        'Supernatural Thrillers': 'Show / Game show',
        'Suspense': 'Show / Game show',
        'Talk & Variety': 'Talk show',
        'Teen Comedies': 'Show / Game show',
        'Teen Dramas': 'Show / Game show',
        'Travel & Adventure Documentaries': 'Documentary',
        'Travel': 'Tourism/Travel',
        'Vampires': 'Show / Game show',
        'Video Gameplay & Walkthroughs': 'New media',
        'Video Games': 'New media',
        'Werewolves': 'Show / Game show',
        'Westerns': 'Show / Game show',
        'Women\'s Interest': 'Show / Game show',
        'World': 'Serious music / Classical music',
        'Zombies': 'Show / Game show'
    }

    if xtype == 'film':
        if subgenre in moviedict:
            catlist.append(moviedict[subgenre])
    else:
        if subgenre in tvdict:
            catlist.append(tvdict[subgenre])

    catlist = set(catlist)
    return catlist

def hextoangle(hexc):
    ''' change hex value to circular degree '''
    hexvalue = int(hexc, 16)
    anglevalue = hexvalue/255*360
    anglevalue = round(anglevalue)
    return anglevalue

def piconget(pid, mnpicon, picndir, piconslug, hxclr1, hxclr2, mangle=None,
             colrful=False, brite=False):
    """ Function for fetching and manipulating picons """

    if direxists(picndir):
        urlbase = "http://images.pluto.tv/channels/"
        if mnpicon:
            urlend = 'solidLogoPNG.png'
        else:
            urlend = 'colorLogoPNG.png'

        geturl = urlbase + "/" + pid + "/" + urlend
        savename = picndir + piconslug + ".png"

        if (not fileexists(savename, False)) or (overwritepicons):
            _f = urllib.request.urlopen(geturl)

            if colrful or brite or hxclr1:

                if colrful or brite:
                    hex1 = pid[-2:]
                    angle1 = hextoangle(hex1)
                    if angle1 - 60 <= 0:
                        angle2 = angle1 + 300
                    else:
                        angle2 = angle1 - 60
                else:
                    hxclr2 = hxclr1

                with Image() as canvas:
                    library.MagickSetSize(canvas.wand, 576, 576)
                    if CBRIGHT:
                        brpc = '100%'
                        sat = '100%'
                    else:
                        brpc = '30%'
                        sat = '50%'

                    if hxclr2 is not None:
                        grad = "gradient:" + hxclr1 + "-" + hxclr2
                    elif hxclr1 and angle1:
                        grad = "gradient:" +  hxclr1 + "-hsb(" + str(angle1) + \
                               ", 100%, " + str(brpc) + ")"
                    else:
                        grad = "gradient:hsb(" + str(angle1) + ", " + sat + ", " + \
                               str(brpc) + ")" + "-hsb(" + str(angle2) + ", " + sat + \
                               ", " + str(brpc) + ")"
                    if mangle:
                        angle1 = mangle


                    canvas.options['gradient:angle'] = str(angle1)
                    canvas.pseudo(576, 576, grad)

                    with Image(file=_f) as img:

                        img.background_color = Color('transparent')
                        img.extent(width=576, height=576, x=0, y=-144)
                        img.composite(canvas, operator='dst_over', left=0, top=0)
                        img.save(filename=savename)

            else:
                with Image(file=_f) as img:
                    img.background_color = Color('transparent')
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
    # it's under 30 mins old and not an empty file
    now = time.time()
    mtime = os.path.getmtime(cchepath)
    if now - mtime <= 1800:
        return False
    return True


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
    if os.path.exists(cachepath):
        if not newcache(cachepath):
            logging.info("Using %s, it's under 30 minutes old.", cachepath)
        else:
            getnewdata()
    else:
        getnewdata()

    with open(cachepath, encoding='utf-8') as _f:
        data = json.load(_f)
        if not debugmode:
            if direxists(localdir):
                m3ufile = open(m3u8path, 'w')
                m3ufile.write("#EXTM3U\n")
        else:
            debugm3u = "#EXTM3U\n"

        xml = lmntree.Element('tv', \
        attrib={"generator-info-name":"Zang's Pluto.TV TVHeadend generator",\
                "generator-info-url":"https://github.com/zang74/PlutoIPTV"})

        badchannels = ["Announcement", "Privacy Policy", "Inside Vizio"]


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
                        'serverSideAds': 'false',
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
                        logo = "file://" + picondir + piconslug + ".png"
                        piconget(deviceid, monopicon, picondir, piconslug,
                                 HEXCOLOUR1, HEXCOLOUR2, angle, COLOURFUL, CBRIGHT)

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
                    xmlicon = "file://" + picondir + piconslug + ".png"
                elif monopicon:
                    xmlicon = channel['solidLogoPNG']['path']
                else:
                    xmlicon = channel['colorLogoPNG']['path']

                lmntree.SubElement(xmlchannel, "icon", src=xmlicon)

                for episodes in channel['timelines']:

                    epdescription = episodes['episode']['description']
                    epdescription = epdescription.replace('\x92', '')

                    epcategory = channel['category']
                    eptype = episodes['episode']['series']['type']
                    epsubgenre = episodes['episode']['subGenre']

                    epcats = tvhcategory(eptype, epcategory, epsubgenre)

                    eppremiere = episodes['episode']['firstAired']
                    tpremiere = datetime.fromisoformat(eppremiere[:-1])
                    epdate = tpremiere.strftime("%Y%m%d")
                    eptitle = episodes['episode']['name']
                    eprating = episodes['episode']['rating']
                    epshow = episodes['title']
                    duration = episodes['episode']['duration']
                    epstart = episodes['start']
                    epstop = episodes['stop']
                    epnumber = episodes['episode']['number']
                    # epicon = episodes['episode']['number']
                    starttime = datetime.fromisoformat(epstart[:-1])
                    localstart = starttime.strftime("%Y%m%d%H%M%S %z")
                    stoptime = datetime.fromisoformat(epstop[:-1])
                    localstop = stoptime.strftime("%Y%m%d%H%M%S %z")
                    # idslug = channel['slug'] + ".plutotv"
                    if channel['category'] == "Latino":
                        eplang = "es"
                    else:
                        eplang = "en"

                    logging.info('Adding instance of %s to channel %s.',
                                 eptitle, channel['name'])

                    eptime = duration / 1000 / 60

                    #tvhcategories()

                    xmlepisode = lmntree.SubElement(
                        xml, "programme", start=localstart, stop=localstop,
                        channel=tvgidslug
                        )
                    lmntree.SubElement(xmlepisode, "title",
                                       lang=eplang).text = epshow
                    if eptitle:
                        lmntree.SubElement(xmlepisode, "sub-title",
                                           lang=eplang).text = eptitle
                    lmntree.SubElement(xmlepisode, "desc",
                                       lang=eplang).text = epdescription
                    # xmlcredits = lmntree.SubElement(xmlepisode, "credits")
                    lmntree.SubElement(xmlepisode, "date").text = epdate

                    for cat in epcats:
                        lmntree.SubElement(xmlepisode, "category", lang=eplang).text = cat

                    lmntree.SubElement(xmlepisode, "length",
                                       units='minutes').text = str(eptime)
                    lmntree.SubElement(xmlepisode, "episode-num",
                                       system='onscreen').text = str(epnumber)
                    xmlrating = lmntree.SubElement(xmlepisode, "rating", system='US')
                    lmntree.SubElement(xmlrating, "value").text = eprating
            else:
                logging.info("Skipping 'fake' channel %s.", channel['name'])
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
        root[:] = sorted(root, key=lambda child:
                         (child.tag, child.get('id'), child.get('channel')))
        xmldata = lmntree.tostring(root, pretty_print=True, encoding="utf-8",
                                   xml_declaration=True,
                                   doctype='<!DOCTYPE tv SYSTEM "xmltv.dtd">')
        if not debugmode:
            with open(epgpath, "wb") as fxml:
                fxml.write(xmldata)
                fxml.close()
                logging.info("Success! Wrote the EPG to %s!", epgpath)
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
