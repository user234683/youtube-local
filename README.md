# youtube-local

![screenshot](https://user-images.githubusercontent.com/28744867/42791028-dabb709a-8922-11e8-935b-6680541e08e4.png)
youtube-local is a browser-based client written in Python for watching Youtube anonymously and without the lag of Polymer (the javascript Youtube uses). One of the primary features is that all requests are routed through Tor, except for the video file at googlevideo.com. This is analogous to what HookTube does, except that you do not have to trust a third-party to respect your privacy. The assumption here is that Google won't put the effort in to incorporate the video file requests into their survelliance systems, as it's not worth pursuing the incredibly small number of users who care about privacy. Using Tor is optional; when not routing through Tor, video pages load *faster* than they do with Youtube's Polymer (for me atleast).

The Youtube API is not used, so no keys or anything are needed. It uses the same requests as the Youtube webpage. No javascript is used either.

Additionally, playlists can be created, and these are stored locally on your computer. The problem with creating playlists on Youtube's servers is (1) they're datamined and (2) videos frequently get deleted by Youtube and lost from the playlist (making it very difficult to find a reupload as the title of the deleted video is not displayed).

## Installing

### Windows

Download the zip file under the Releases page. Unzip it anywhere you choose, it's completely portable. No registry changes or whatnot are made.

### Linux/MacOS

Ensure you have python 3.5 or later installed. Then, install gevent, brotli, and PySocks by running
```
pip3 install gevent brotli pysocks
```
**Note**: If pip isn't installed, install it according to [this answer](https://unix.stackexchange.com/a/182467), but make sure you run `python3 get-pip.py` instead of `python get-pip.py`

Download the tarball under the Releases page and extract it.

## Usage

On windows, open run.bat. On Linux/MacOS, run `python3 server.py`.
**Note**: On Linux/MacOS, you may need root in order for it to listen for http connections on port 80 (as it is an http server that listens only for connections from your machine). This is not recommended, as this program isn't safe from exploits which can coerce it to run arbitrary code as root. Instead, you should change `port_number = 80` in settings.txt to a port higher than 1024 (such as 8080). See [here](https://serverfault.com/questions/112795/how-to-run-a-server-on-port-80-as-a-normal-user-on-linux) for more information. You'll also need to use that port number when accessing the webpage from the browser.

Access youtube URLs by prefixing them with `localhost/`, For instance, `http://localhost/https://www.youtube.com/watch?v=vBgulDeV2RU`
You can use an addon such as [Redirector](https://addons.mozilla.org/en-US/firefox/addon/redirector/) to automatically redirect Youtube URLs to youtube-local. I use the include pattern `^(https?://(?:[a-zA-Z0-9_-]*\.)?(?:youtube\.com|youtu\.be)/.*)` and the redirect pattern `http://localhost/$1`. I also exlude `^https?://(?:[a-zA-Z0-9_-]*\.)?youtube\.com/feed/subscriptions` for subscriptions.

Local playlists are found at http://localhost/youtube.com/playlists

youtube-local can be added as a search engine in firefox to make searching more convenient. See [here](https://support.mozilla.org/en-US/kb/add-or-remove-search-engine-firefox) for information on firefox search plugins.

### Using Tor

Change `route_tor = False` to `route_tor = True` in settings.txt to enable Tor routing.
If settings.txt doesn't exist yet, run the program and it will be created with the default settings.

Ensure tor is listening for Socks5 connections on port 9050 (a simple way to accomplish this is by opening the Tor Browser Bundle and leaving it open). Your connections should now be routed through Tor.

## Planned Features

- Options for saving playlists
- Settings
- Subscriptions
- Posting comments
- And others I couldn't think of when making this list

Pull requests and issues are welcome

## Screenshots
[Channel](https://user-images.githubusercontent.com/28744867/42792117-bb8d7e9c-8928-11e8-8776-60076a7ad3de.png)

[Video/Audio Downloading](https://user-images.githubusercontent.com/28744867/42792131-c5a4999c-8928-11e8-8f50-0161ea15067c.png)
## License

This project is licensed under the GNU Affero General Public License v3 (GNU AGPLv3) or any later version.

Permission is hereby granted to the youtube-dl project at https://github.com/rg3/youtube-dl to relicense any portion of this software under the Unlicense, public domain, or whichever license is in use by youtube-dl at the time of relicensing, for the purpose of inclusion of said portion into youtube-dl. Relicensing permission is not granted for any purpose outside of direct inclusion into the [official repository](https://github.com/rg3/youtube-dl) of youtube-dl. If inclusion happens during the process of a pull-request, relicensing happens at the moment the pull request is merged into youtube-dl; until that moment, any cloned repositories of youtube-dl which make use of this software are subject to the terms of the GNU AGPLv3.

## Similar projects
- [youtube-dl](https://rg3.github.io/youtube-dl/), which this project is based off
- [NewPipe](https://newpipe.schabi.org/) (app for android)
- [mps-youtube](https://github.com/mps-youtube/mps-youtube) (terminal-only program)
- [youtube-viewer](https://github.com/trizen/youtube-viewer)
- [FreeTube](https://github.com/FreeTubeApp/FreeTube)
- [smtube](https://www.smtube.org/)
- [Minitube](https://flavio.tordini.org/minitube), [github here](https://github.com/flaviotordini/minitube)
- [toogles](https://github.com/mikecrittenden/toogles) (only embeds videos, doesn't use mp4)
- [goyt](https://gitgud.io/m712/goyt/)
- [invidious](https://github.com/omarroth/invidious)
