#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import json
import os
import time
import requests
import urllib.request
import urllib.parse
from urllib.parse import urlencode
import logging
from datetime import datetime,timezone
import wget
import uuid
from furl import furl
from lxml import etree as lmntree
import pytz
from tzlocal import get_localzone
import argparse
import pathlib
from decimal import *
import re
from wand.image import Image
from wand.color import Color


parser = argparse.ArgumentParser()
parser.add_argument('--debugmode', default=False, action='store_true', help="Debug mode")
parser.add_argument('-d', '--dir', dest='localdir', help="Path to M3U directory")
parser.add_argument('-c', '--cache', dest='cachedir', help="Path to cache directory")
parser.add_argument('-e', '--epg', dest='epgdir', help="Path to EPG directory")
parser.add_argument('-l', '--log', dest='logdir', help="Path to log directory")
parser.add_argument('-i', '--picondir', dest='picondir', help="Path to picon cache directory")
parser.add_argument('-f', '--color', '--colour', dest='hexcolour', default='transparent', help="Colour in hex #1E1E1E format for image background")
parser.add_argument('-m', '--monopicon', dest='monopicon', default=False, action='store_true', help="Use monochrome (all-white) picon")
parser.add_argument('-w', '--overwritepicons', dest='overwritepicons', default=False, action='store_true', help="Replace existing picons with newly downloaded versions")
parser.add_argument('-t', '--time', dest='epghours', help="Number of EPG Hours to collect")
parser.add_argument('-x', '--longitude', dest='xlong', default=0, help="Longitude in decimal format")
parser.add_argument('-y', '--latitude', dest='ylat', default=0, help="Latitude in decimal format")
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
epghours = args.epghours
xlong = str(args.xlong)
ylat = str(args.ylat)
m3u8file = "plutotv.m3u8"
cachefile = "plutocache.json"
epgfile = "plutotvepg.xml"
logfile = "plutotv.log"
defaultepghours = 8
maxepghours = 10


level = logging.INFO


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
	level = logging.DEBUG

cachepath = os.path.join(cachedir,cachefile)
m3u8path = os.path.join(localdir,m3u8file)
epgpath = os.path.join(epgdir,epgfile)
logpath = os.path.join(logdir,logfile)

fourplaces = Decimal(10) ** -4
xlong = Decimal(xlong).quantize(fourplaces)
ylat = Decimal(ylat).quantize(fourplaces)  

handlers = [logging.FileHandler(logpath,'w'), logging.StreamHandler()]
logging.basicConfig(level=level,format='[%(levelname)s]: %(message)s',handlers=handlers)

if debugmode:
	xyused = "Longitude used: " + str(xlong) + ", Latitude used: " + str(ylat)
	logging.debug(xyused)

if epghours:
	# check for --hours argument
	if not epghours.isdigit():
		logging.error("Hours argument must be an integer.")
		exit()
	if int(epghours) > maxepghours:
		hourswarn = "Hours argument cannot be longer than " +  str(maxepghours) + ". Using max value."
		logging.warning(hourswarn)
		epghours = maxepghours
else:
	epghours = defaultepghours
	hourswarn = "Fetching default EPG of " +  str(defaultepghours) + " hours."
	logging.warning(hourswarn)

if debugmode:
	hoursused = 'Episode Hours supplied: ' + str(epghours)
	logging.debug(hoursused)


if debugmode:
	if not os.path.isdir(debugdir):
		os.mkdir(debugdir)
	debugcachepath = "Cache Path: " + debugdir + "/" + cachefile
	logging.debug(debugcachepath)
	debugm3u8path = "M3u8 Path: " + debugdir + "/" + m3u8file
	logging.debug(debugm3u8path)
	debugepgpath = "EPG Path: " + debugdir + "/" + epgpath
	logging.debug(debugepgpath)
	debuglogpath = 'Log Path: ' + debugdir + "/"
	logging.debug(debuglogpath)


def exists(ipath,create=False):
	fpath, fname = os.path.split(ipath)
	try:
		st = os.stat(fpath)
		try:
			stt = os.access(fpath, os.W_OK)
		except:
			logging.error("Write permissions on path " + fpath + " are incorrect. Exiting.")
			exit()
	except os.error:
		logging.warning("Path " + fpath + " doesn't exist. Creating")
		try: 
			srr = os.mkdir(fpath)
		except:
			logging.error("Can't create directory " + fpath)
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
					temp = open(ipath,"w")
					temp.close()
					return True
				except:
					logging.error("Can't create file " + ipath)
					exit()
	return True

def piconget(pid,monopicon,picondir,piconslug,hexcolour):
	if exists(picondir):
		urlbase = "http://images.pluto.tv/channels/"
		if monopicon:
			urlend = 'solidLogoPNG.png'
		else:		
			urlend = 'colorLogoPNG.png'
	
		geturl = urlbase + "/" + pid + "/" + urlend
		savename = picondir + piconslug + ".png"
		print(savename)
		
		if not exists(savename) or overwritepicons:
			f = urllib.request.urlopen(geturl)
			with Image(file=f) as img:
				result = re.match("^(?:#)?[0-9a-fA-F]{3,6}$",str(hexcolour))
				if result:
					if not hexcolour.startswith("#"):
						hexcolour = "#" + hexcolour
					img.background_color = Color(hexcolour)
				elif hexcolour == "transparent":
					img.background_color = Color('transparent')
				else:
					logging.error("Background colour option must follow '#FFFFFF' hex format")
					exit()
				img.extent(width=576, height=576, x=0, y=-144)	
				img.save(filename=savename)
			f.close()
	else:
		try:
			os.mkdir(picondir)
		except os.error:
			print ("Could not create " + picondir)
def newcache(cachepath):
	if os.path.isfile(cachepath):
	
	# it's under 30 mins old and not an empty file
		now = time.time()
		mtime = os.path.getmtime(cachepath)
		if (now - mtime <= 1800):
			return False
		else:
			return True
	else:
		return True
		
def getnewdata():
	try:
		os.remove(cachepath)	
	except:
		pass
	tdelta = int(epghours)*60*60
	now = time.time()
	later = now + tdelta
	# 2020-03-24%2021%3A00%3A00.000%2B0000
	  
	starttime = urllib.parse.quote(datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:00:00.000+0000'))

	# 2020-03-25%2005%3A00%3A00.000%2B0000
	stoptime = urllib.parse.quote(datetime.fromtimestamp(later).strftime('%Y-%m-%d %H:00:00.000+0000'))

	
	url = "http://api.pluto.tv/v2/channels?start=" + starttime + "&stop=" + stoptime

	if debugmode:
		logging.debug(url)
	
	logging.debug("Using api.pluto.tv, writing " + cachefile + ".")
	try:
		wget.download(url, out=cachepath)
	except:
		logging.error("There was an issue downloading EPG data. Exiting.")
		exit()

def datetime_from_utc_to_local(utc_datetime):
	now_timestamp = time.time()
	offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
	return utc_datetime + offset


def main():

	logging.info('Grabbing EPG...')

	if newcache(cachepath) == False:
		logging.info("Using " + cachepath + ", it's under 30 minutes old.")
	else:
		getnewdata()
	
	with open(cachepath) as f:
		data = json.load(f)
		if not debugmode:
			m3ufile = open(m3u8path, 'w')
			m3ufile.write("#EXTM3U\n")	
		else:
			debugm3u = "#EXTM3U\n"
		
		xml = lmntree.Element('tv', attrib={"generator-info-name":"Zang's Pluto.TV TVHeadend generator","generator-info-url":"https://github.com/zang74/PlutoIPTV"})

		for channel in data:

			# M3U8 Playlist 

			if channel['isStitched'] == True:
				if not channel['name'] == 'Announcement':
					deviceid = channel['_id']
					chnumber = str(channel['number'])
					# deviceid = uuid.uuid1()
					# sid = uuid.uuid4()
					sid = chnumber
					baseurl = furl(channel['stitched']['urls'][0]['url']).remove(args=True, fragment=True).url
					if not str(xlong) and not str(ylat):
						l = furl(channel['stitched']['urls'][0]['url'])
						xnewlong = l.args['deviceLat']
						ynewlat = l.args['deviceLon']
					else:
						xnewlong = str(xlong)
						ynewlat = str(ylat)
				
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
						piconget(deviceid,monopicon,picondir,piconslug,hexcolour)

					m3uoutput = "\n#EXTINF:-1 tvg-name=\"" + chname + "\" tvg-id=\"" + deviceid + ".plutotv\" tvg-logo=\"" + logo + "\" group-title=\"" + group + "\"," + chname + "\n" + m3uurl + "\n"
							
					logging.info('Adding ' + chname + ' channel.')
			
					if not debugmode:
						m3ufile.write(m3uoutput)
					else:
						debugm3u += m3uoutput	
				else:
					logging.info("Skipping 'fake' channel " + channel['name'] + '.')
		
				# XMLTV EPG
		
				tvgidslug = channel['_id'] + ".plutotv"
				xmlchannel = lmntree.SubElement (xml, "channel", id=tvgidslug)
				lmntree.SubElement(xmlchannel, "display-name").text = channel['name']

				if picondir:
					xmlicon = picondir + piconslug + ".png"
				elif monopicon:
					xmlicon = channel['solidLogoPNG']['path']		
				else:
					xmlicon = channel['colorLogoPNG']['path']

				lmntree.SubElement(xmlchannel, "icon",src=xmlicon)
		
				for episodes in channel['timelines']:
	
					categorylist = []
					epdescription = episodes['episode']['description']
					epdescription = epdescription.replace('\x92','')
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
					epicon = episodes['episode']['number']
					starttime = datetime.fromisoformat(epstart[:-1])
					tstart = localtimezone.localize(starttime)
					localstart = tstart.strftime("%Y%m%d%H%M%S %z")
					stoptime = datetime.fromisoformat(epstop[:-1])
					tstop = localtimezone.localize(stoptime)
					localstop = tstop.strftime("%Y%m%d%H%M%S %z")
					idslug = channel['slug'] + ".plutotv"
					if channel['category']  == "Latino":
						eplang = "es"
					else:
						eplang = "en"
			
					logging.info('Adding instance of ' + eptitle + ' to channel ' + channel['name'] + '.')

					eptime = duration / 1000 / 60

					xmlepisode = lmntree.SubElement(xml, "programme", start=localstart, stop=localstop, channel=tvgidslug)
					lmntree.SubElement(xmlepisode, "title", lang=eplang).text = epshow
					if eptitle:
						lmntree.SubElement(xmlepisode, "sub-title", lang=eplang).text = eptitle
					lmntree.SubElement(xmlepisode, "desc", lang=eplang).text = epdescription
					xmlcredits = lmntree.SubElement(xmlepisode, "credits")
					lmntree.SubElement(xmlepisode, "date").text = epdate
					for cat in categorylist:
						lmntree.SubElement(xmlepisode, "category", lang=eplang).text = cat
					lmntree.SubElement(xmlepisode, "length", units='minutes').text = str(eptime)
					lmntree.SubElement(xmlepisode, "episode-num", system='onscreen').text = str(epnumber)
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
			

		logging.info('Success! Wrote the M3U8 tuner to ' + m3u8path + "!")
		xmltvtree = lmntree.ElementTree(xml)
		
		root = xmltvtree.getroot()

		# sort the first layer
		root[:] = sorted(root, key=lambda child: (child.tag,child.get('id'),child.get('channel')))



		
		xmldata = lmntree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True, doctype='<!DOCTYPE tv SYSTEM "xmltv.dtd">')
		if not debugmode:
			with open(epgpath, "wb") as f:
				f.write(xmldata)
				f.close()
				logging.info('Success! Wrote the EPG to ' + m3u8path + "!")
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
