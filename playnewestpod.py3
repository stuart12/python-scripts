#!/usr/bin/python3
# playnewestpod Copyright (c) 2015 Stuart Pook (http://www.pook.it/)
# play the most recent podcast from a feed url
# set noexpandtab copyindent preserveindent softtabstop=0 shiftwidth=4 tabstop=4
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import argparse
import sys
import subprocess
import collections
import podcastparser
import time
import tempfile
import datetime
import urllib.request

def myname():
    return os.path.basename(sys.argv[0])

def verbose(options, level, *message):
    if options.verbosity >= level:
        print(myname() + ":", *message, file=sys.stderr)

PlayAble = collections.namedtuple('PlayAble', ['date', 'guid', 'url', 'feed', 'channel', 'title'])

def scan(feedurl, played, options):
    verbose(options, 1, "scanning", feedurl)
    podcasts = []
    parsed = podcastparser.parse(feedurl, urllib.request.urlopen(feedurl))
    channel = parsed['title']
    for episode in parsed['episodes']:
        guid = episode['guid']
        if guid and not guid in played:
            for enclosure in episode['enclosures']:
                if enclosure['mime_type'].startswith('audio/'):
                    date = int(episode['published'])
                    p = PlayAble(date, guid, enclosure['url'], feedurl, channel, episode['title'])
                    podcasts.append(p)
                    verbose(options, 2, p)
    return podcasts

def play(playable, played, options):
    with tempfile.NamedTemporaryFile(mode="w", prefix='playnpod', suffix='.m3u8') as tmp:
        print('#EXTM3U8', file=tmp)
        print('#EXTINF:0,' + playable.channel + ":",
                playable.title,
                datetime.date.fromtimestamp(playable.date).strftime(options.datefmt),
                "(" + os.path.splitext(os.path.basename(playable.feed))[0] + ")",
                file=tmp)
        print(playable.url, file=tmp)
        tmp.flush()
        cmd = subprocess.Popen([options.player, options.player_option, tmp.name])
        try:
            r = cmd.wait(options.min_play_time)
        except subprocess.TimeoutExpired:
            print(playable.guid, file=played)
            played.flush()
            r = cmd.wait()
        else:
            if r == 0:
                print(playable.guid, file=played)
                played.flush()
        if r != 0:
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="play the most recent podcast")

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("--min_play_time", metavar="SECONDS", type=int, default=9,
            help="minimum to consider a podcast played")
    parser.add_argument("--player", metavar="COMMAND", default="videolan", help="command to play a url")
    parser.add_argument("--player_option", metavar="OPTION", default="--play-and-exit", help="option for command to play a url")
    parser.add_argument("--datefmt", metavar="STRFTIME", default="%d/%m/%Y", help="strftime format for dates")
    parser.add_argument("--cache", metavar="DIRECTORY", default=os.path.expanduser("~/.cache/playnewestpod"),
            help="stock list of played podcasts")
    parser.add_argument("--config", metavar="DIRECTORY", default=os.path.expanduser("~/.config/playnewestpod"),
            help="stock list of url podcasts")
    parser.add_argument('-a', "--add", action="store_true", help="add podcast urls to list")
    parser.add_argument("--loop", action="store_true", help="play all podcasts")

    parser.add_argument('urls', nargs=argparse.REMAINDER, help='urls to (permanently) add to the play list')

    options = parser.parse_args()
    podcasts = os.path.join(options.config, "podcasts")
    if options.add:
        with open(podcasts, "a+") as out:
            for url in options.urls:
                print(url, file=out)
    else:
        with open(os.path.join(options.cache, "played"), "r+") as played:
            played.seek(0)
            already_played = frozenset(line.strip() for line in played)
            playables = []
            if options.urls:
                for url in options.urls:
                    playables.extend(scan(url, already_played, options))
            else:
                with open(podcasts) as pods:
                    for pod in pods:
                        playables.extend(scan(pod.strip(), already_played, options))
            playables.sort(key=lambda x: -x.date)
            for playable in playables:
                play(playable, played, options)
                if not options.loop:
                    break

if __name__ == "__main__":
    main()
