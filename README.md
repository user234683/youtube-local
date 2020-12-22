# youtube-local

![screenshot](https://user-images.githubusercontent.com/28744867/64483429-8a890780-d1b6-11e9-8423-6956ff7c588d.png)
youtube-local is a browser-based client written in Python for watching Youtube anonymously and without the lag of the slow page used by Youtube. One of the primary features is that all requests are routed through Tor, except for the video file at googlevideo.com. This is analogous to what HookTube (defunct) and Invidious do, except that you do not have to trust a third-party to respect your privacy. The assumption here is that Google won't put the effort in to incorporate the video file requests into their tracking, as it's not worth pursuing the incredibly small number of users who care about privacy (Tor video routing is also provided as an option). Tor has high latency, so this will not be as fast network-wise as regular Youtube. However, using Tor is optional; when not routing through Tor, video pages may load faster than they do with Youtube's page depending on your browser.

The Youtube API is not used, so no keys or anything are needed. It uses the same requests as the Youtube webpage.

## Screenshots
[Gray theme](https://user-images.githubusercontent.com/28744867/64483431-8e1c8e80-d1b6-11e9-999c-14d36ddd582f.png)

[Dark theme](https://user-images.githubusercontent.com/28744867/64483432-8fe65200-d1b6-11e9-90bd-32869542e32e.png)

[Non-Theater mode](https://user-images.githubusercontent.com/28744867/64483433-92e14280-d1b6-11e9-9b56-2ef5d64c372f.png)

[Channel](https://user-images.githubusercontent.com/28744867/64483436-95dc3300-d1b6-11e9-8efc-b19b1f1f3bcf.png)

[Downloads](https://user-images.githubusercontent.com/28744867/64483437-a2608b80-d1b6-11e9-9e5a-4114391b7304.png)

## Features
* Standard pages of Youtube: search, channels, playlists
* Anonymity from Google's tracking by routing requests through Tor
* Local playlists: These solve the two problems with creating playlists on Youtube: (1) they're datamined and (2) videos frequently get deleted by Youtube and lost from the playlist, making it very difficult to find a reupload as the title of the deleted video is not displayed.
* Themes: Light, Gray, and Dark
* Subtitles
* Easily download videos or their audio
* No ads
* View comments
* Works without Javascript
* Theater and non-theater mode
* Subscriptions that are independent from Youtube
  * Can import subscriptions from Youtube
  * Works by checking channels individually
  * Can be set to automatically check channels.
  * For efficiency of requests, frequency of checking is based on how quickly channel posts videos
  * Can mute channels, so as to have a way to "soft" unsubscribe. Muted channels won't be checked automatically or when using the "Check all" button. Videos from these channels will be hidden.
  * Can tag subscriptions to organize them or check specific tags
* Fast page
  * No distracting/slow layout rearrangement
  * No lazy-loading of comments; they are ready instantly.
* Settings allow fine-tuned control over when/how comments or related videos are shown:
  1. Shown by default, with click to hide
  2. Hidden by default, with click to show
  3. Never shown
* Optionally skip sponsored segments using [SponsorBlock](https://github.com/ajayyy/SponsorBlock)'s API
* Custom video speeds
* Video transcript

## Planned features
- [ ] Putting videos from subscriptions or local playlists into the related videos
- [x] Information about video (geographic regions, region of Tor exit node, etc)
- [ ] Ability to delete playlists
- [ ] Auto-saving of local playlist videos
- [ ] Import youtube playlist into a local playlist
- [ ] Rearrange items of local playlist
- [ ] Video qualities other than 360p and 720p by muxing video and audio
- [ ] Corrected .m4a downloads
- [x] Indicate if comments are disabled
- [x] Indicate how many comments a video has
- [ ] Featured channels page
- [ ] Channel comments
- [x] Video transcript
- [ ] Automatic Tor circuit change when blocked
- [x] Support &t parameter
- [ ] Subscriptions: Option to mark what has been watched
- [ ] Subscriptions: Option to filter videos based on keywords in title or description
- [ ] Subscriptions: Delete old entries and thumbnails

## Installing

### Windows

Download the zip file under the Releases page. Unzip it anywhere you choose.

### Linux/MacOS

Download the tarball under the Releases page and extract it. `cd` into the directory and run
```
pip3 install -r requirements.txt
```

**Note**: If pip isn't installed, first try installing it from your package manager. Make sure you install pip for python 3. For example, the package you need on debian is python3-pip rather than python-pip. If your package manager doesn't provide it, try to install it according to [this answer](https://unix.stackexchange.com/a/182467), but make sure you run `python3 get-pip.py` instead of `python get-pip.py`

## Usage

Firstly, if you wish to run this in portable mode, create the empty file "settings.txt" in the program's main directory. If the file is there, settings and data will be stored in the same directory as the program. Otherwise, settings and data will be stored in `C:\Users\[your username]\.youtube-local` on Windows and `~/.youtube-local` on Linux/MacOS.

To run the program on windows, open `run.bat`. On Linux/MacOS, run `python3 server.py`.


Access youtube URLs by prefixing them with `http://localhost:8080/`, For instance, `http://localhost:8080/https://www.youtube.com/watch?v=vBgulDeV2RU`
You can use an addon such as Redirector ([Firefox](https://addons.mozilla.org/en-US/firefox/addon/redirector/)|[Chrome](https://chrome.google.com/webstore/detail/redirector/ocgpenflpmgnfapjedencafcfakcekcd)) to automatically redirect Youtube URLs to youtube-local. I use the include pattern `^(https?://(?:[a-zA-Z0-9_-]*\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/.*)` and the redirect pattern `http://localhost:8080/$1` (Make sure you're using regular expression mode).

If you want embeds on the web to also redirect to youtube-local, make sure "Iframes" is checked under advanced options in your redirector rule.

youtube-local can be added as a search engine in firefox to make searching more convenient. See [here](https://support.mozilla.org/en-US/kb/add-or-remove-search-engine-firefox) for information on firefox search plugins.

### Using Tor

In the settings page, set "Route Tor" to "On, except video" (the second option). Be sure to save the settings.

Ensure Tor is listening for Socks5 connections on port 9150 (a simple way to accomplish this is by opening the Tor Browser Bundle and leaving it open). Your connections should now be routed through Tor.

### Tor video routing

If you wish to route the video through Tor, set "Route Tor" to "On, including video". Because this is bandwidth-intensive, you are strongly encouraged to donate to the [consortium of Tor node operators](https://torservers.net/donate.html). For instance, donations to [NoiseTor](https://noisetor.net/) go straight towards funding nodes. Using their numbers for bandwidth costs, together with an average of 485 kbit/sec for a diverse sample of videos, and assuming n hours of video watched per day, gives $0.03n/month. A $1/month donation will be a very generous amount to not only offset losses, but help keep the network healthy.

In general, Tor video routing will be slower (for instance, moving around in the video is quite slow). I've never seen any signs that watch history in youtube-local affects on-site Youtube recommendations. It's likely that requests to googlevideo are logged for some period of time, but are not integrated into Youtube's larger advertisement/recommendation systems, since those presumably depend more heavily on in-page tracking through Javascript rather than CDN requests to googlevideo.

## Contributing

Pull requests and issues are welcome

For coding guidelines and an overview of the software architecture, see the HACKING.md file.

## License

This project is licensed under the GNU Affero General Public License v3 (GNU AGPLv3) or any later version.

Permission is hereby granted to the youtube-dl project at [https://github.com/ytdl-org/youtube-dl](https://github.com/ytdl-org/youtube-dl) to relicense any portion of this software under the Unlicense, public domain, or whichever license is in use by youtube-dl at the time of relicensing, for the purpose of inclusion of said portion into youtube-dl. Relicensing permission is not granted for any purpose outside of direct inclusion into the [official repository](https://github.com/ytdl-org/youtube-dl) of youtube-dl. If inclusion happens during the process of a pull-request, relicensing happens at the moment the pull request is merged into youtube-dl; until that moment, any cloned repositories of youtube-dl which make use of this software are subject to the terms of the GNU AGPLv3.

## Similar projects
- [youtube-dl](https://rg3.github.io/youtube-dl/), which this project was based off
- [invidious](https://github.com/iv-org/invidious) Similar to this project, but also allows it to be hosted as a server to serve many users
- [NewPipe](https://newpipe.schabi.org/) (app for android)
- [mps-youtube](https://github.com/mps-youtube/mps-youtube) (terminal-only program)
- [youtube-viewer](https://github.com/trizen/youtube-viewer)
- [FreeTube](https://github.com/FreeTubeApp/FreeTube) (Similar to this project, but is an electron app outside the browser)
- [smtube](https://www.smtube.org/)
- [Minitube](https://flavio.tordini.org/minitube), [github here](https://github.com/flaviotordini/minitube)
- [toogles](https://github.com/mikecrittenden/toogles) (only embeds videos, doesn't use mp4)
- [Yotter](https://github.com/ytorg/Yotter) Similar to this project and to invidious. Also supports Twitter
