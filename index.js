#!/usr/bin/env node

const request = require('request');
const j2x = require('jsontoxml');
const moment = require('moment');
const fs = require('fs-extra');
const url = require('url');

const plutoIPTV = {
  grabJSON: function(callback) {
    callback = callback || function() {};

    console.log('[INFO] Grabbing EPG...');

    // check for cache
    if (fs.existsSync('cache.json')) {
      let stat = fs.statSync('cache.json');

      let now = new Date() / 1000;
      let mtime = new Date(stat.mtime) / 1000;

      // it's under 30 mins old
      if (now - mtime <= 1800) {
        console.log("[DEBUG] Using cache.json, it's under 30 minutes old.");

        callback(false, fs.readJSONSync('cache.json'));
        return;
      }
    }

    // 2020-03-24%2021%3A00%3A00.000%2B0000
    let startTime = encodeURIComponent(
      moment().format('YYYY-MM-DD HH:00:00.000ZZ')
    );

    // 2020-03-25%2005%3A00%3A00.000%2B0000
    let stopTime = encodeURIComponent(
      moment()
        .add(8, 'hours')
        .format('YYYY-MM-DD HH:00:00.000ZZ')
    );

    let url = `http://api.pluto.tv/v2/channels?start=${startTime}&stop=${stopTime}`;

    console.log(url);

    request(url, function(err, code, raw) {
      console.log('[DEBUG] Using api.pluto.tv, writing cache.json.');
      fs.writeFileSync('cache.json', raw);

      callback(err || false, JSON.parse(raw));
      return;
    });
  }
};

module.exports = plutoIPTV;

plutoIPTV.grabJSON(function(err, channels) {
  ///////////////////
  // M3U8 Playlist //
  ///////////////////

  let m3u8 = '';

  channels.forEach(channel => {
    if (channel.isStitched) {
      let m3uUrl = new URL(channel.stitched.urls[0].url);
      let queryString = url.search;
      let params = new URLSearchParams(queryString);

      // set the url params
      params.set('id', '101');
      params.set('advertisingId', '1');
      params.set('appName', 'test');
      params.set('appVersion', 'unknown');
      params.set('architecture', 'x86');
      params.set('buildVersion', '1.0.0');
      params.set('clientTime', '0');
      params.set('deviceDNT', '1');
      params.set('deviceId', '90');
      params.set('deviceLat', '0.0');
      params.set('deviceLon', '0.0');
      params.set('deviceMake', 'test');
      params.set('deviceModel', 'test');
      params.set('deviceType', 'test');
      params.set('deviceVersion', 'test');
      params.set('includeExtendedEvents', 'false');
      params.set('sid', '123');
      params.set('userId', '321');

      m3uUrl.search = params.toString();
      m3uUrl = m3uUrl.toString();

      let slug = channel.slug;
      let logo = channel.solidLogoPNG.path;
      let group = channel.category;
      let name = channel.name;

      m3u8 =
        m3u8 +
        `#EXTINF:0 channel-id="${slug}" tvg-logo="${logo}" group-title="${group}", ${name}
${m3uUrl}

`;

      console.log('[INFO] Adding ' + channel.name + ' channel.');
    } else {
      console.log("[DEBUG] Skipping 'fake' channel " + channel.name + '.');
    }
  });

  ///////////////////////////
  // XMLTV Programme Guide //
  ///////////////////////////
  let tv = [];

  //////////////
  // Channels //
  //////////////
  channels.forEach(channel => {
    tv.push({
      name: 'channel',
      attrs: { id: channel.slug },
      children: [
        { name: 'display-name', text: channel.name },
        { name: 'display-name', text: channel.number },
        { name: 'desc', text: channel.summary },
        { name: 'icon', attrs: { src: channel.solidLogoPNG.path } }
      ]
    });

    //////////////
    // Episodes //
    //////////////

    channel.timelines.forEach(programme => {
      console.log(
        '[INFO] Adding instance of ' +
          programme.title +
          ' to channel ' +
          channel.name +
          '.'
      );

      tv.push({
        name: 'programme',
        attrs: {
          start: moment(programme.start).format('YYYYMMDDHHmmss ZZ'),
          stop: moment(programme.stop).format('YYYYMMDDHHmmss ZZ'),
          channel: channel.slug
        },
        children: [
          { name: 'title', attrs: { lang: 'en' }, text: programme.title },
          {
            name: 'sub-title',
            attrs: { lang: 'en' },
            text:
              programme.title == programme.episode.name
                ? ''
                : programme.episode.name
          },
          {
            name: 'desc',
            attrs: { lang: 'en' },
            text: programme.episode.description
          },
          {
            name: 'date',
            text: moment(programme.episode.firstAired).format('YYYYMMDD')
          },
          {
            name: 'category',
            attrs: { lang: 'en' },
            text: programme.episode.genre
          },
          {
            name: 'category',
            attrs: { lang: 'en' },
            text: programme.episode.subGenre
          },
          {
            name: 'episode-num',
            attrs: { system: 'onscreen' },
            text: programme.episode.number
          }
        ]
      });
    });
  });

  let epg = j2x(
    { tv },
    {
      prettyPrint: true,
      escape: true
    }
  );

  fs.writeFileSync('epg.xml', epg);
  console.log('[SUCCESS] Wrote the EPG to epg.xml!');

  fs.writeFileSync('playlist.m3u8', m3u8);
  console.log('[SUCCESS] Wrote the M3U8 tuner to playlist.m3u8!');
});
