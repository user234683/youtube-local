# Localtube

Localtube is a browser-based client written in Python for watching Youtube anonymously and without the lag of Polymer (the javascript Youtube uses). One of the primary features is that all requests are routed through Tor, except for the video file at googlevideo.com. This is analogous to what HookTube does, except that you do not have to trust a third-party to respect your privacy. The assumption here is that Google won't put the effort in to incorporate the video file requests into their survelliance systems, as it's not worth pursuing the incredibly small number of users who care about privacy. Using Tor is optional; when not routing through Tor, video pages load *faster* than they do with Youtube's Polymer (for me atleast).

Additionally, playlists can be created, and these are stored locally on your computer. The problem with creating playlists on Youtube's servers is (1) they're datamined and (2) videos frequently get deleted by Youtube and lost from the playlist (making it very difficult to find a reupload as the title of the deleted video is not displayed).

## Installing

### Windows

Download the zip file under the Releases page. Unzip it anywhere you choose, it's completely portable. No registry changes or whatnot are made.

### Linux/MacOS

Ensure you have python 3.6 or later installed. Then, install gevent, brotli, and PySocks by running
```
pip install gevent brotli pysocks
```
Download the tarball under the Releases page and extract it.

## Usage

On windows, open run.bat. On Linux/MacOS, run `python server.py`

Access youtube URLs by prefixing them with `localhost/`, For instance, `http://localhost/https://www.youtube.com/watch?v=vBgulDeV2RU`
You can use an addon such as [Redirector](https://addons.mozilla.org/en-US/firefox/addon/redirector/) to automatically redirect Youtube URLs to Localtube. I use the include pattern `^(https?://(?:[a-zA-Z0-9_-]*\.)?(?:youtube\.com|youtu\.be)/.*)` and the redirect pattern `http://localhost/$1`

Local playlists are found at http://localhost/youtube.com/playlists

### Using Tor

Change 
```ROUTE_TOR = False```
to
```ROUTE_TOR = True```
in server.py to enable Tor routing

Ensure tor is listening for Socks5 connections on port 9050 (a simple way to accomplish this is by opening the Tor Browser Bundle and leaving it open). Your connections should now be routed through Tor.

## Planned Features

- Options for saving videos and playlists
- Settings
- Subscriptions
- Posting comments
- And others I couldn't think of when making this list

Pull requests are welcome

## License

This project is licensed under the GNU Affero General Public License v3 (GNU AGPLv3) or any later version.
