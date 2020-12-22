# Coding guidelines
* Follow the [PEP 8 guidelines](https://www.python.org/dev/peps/pep-0008/) for all new Python code as best you can. Some old code doesn't follow PEP 8 yet. This includes limiting line length to 79 characters (with exception for long strings such as URLs that can't reasonably be broken across multiple lines) and using 4 spaces for indentation.

* Do not use single letter or cryptic names for variables (except iterator variables or the like). When in doubt, choose the more verbose option.

* For consistency, use ' instead of " for strings for all new code. Only use " when the string contains ' inside it. Exception: " is used for html attributes in Jinja templates.

* Don't leave trailing whitespaces at the end of lines. Configure your editor the way you need to avoid this from happening.

* Make commits highly descriptive, so that other people (and yourself in the future) know exactly why a change was made. The first line of the commit is a short summary. Add a blank line and then a more extensive summary. If it is a bug fix, this should include a description of what caused the bug and how this commit fixes it. There's a lot of knowledge you gather while solving a problem. Dump as much of it as possible into the commit for others and yourself to learn from. Mention the issue number (e.g. Fixes #23) in your commit if applicable. [Here](https://www.freecodecamp.org/news/writing-good-commit-messages-a-practical-guide/) are some useful guidelines.

* The same guidelines apply to commenting code. If a piece of code is not self-explanatory, add a comment explaining what it does and why it's there.

# Testing and releases
* This project uses pytest. To install pytest and any future dependencies needed for development, run pip3 on the requirements-dev.txt file. To run tests, run `python3 -m pytest` rather than just `pytest` because the former will make sure the toplevel directory is in Python's import search path.

* To build releases for Windows, run `python3 generate_release.py [intended python version here, without v infront]`. The required software (such as 7z, git) are listed in the `generate_release.py` file. For instance, wine is required if building on Linux. The build script will automatically download the embedded Python release to include. Use the latest release of Python 3.7.x so that Vista will be supported. See https://github.com/user234683/youtube-local/issues/6#issuecomment-672608388

# Overview of the software architecture

## server.py
* This is the entry point, and sets up the HTTP server that listens for incoming requests. It delegates the request to the appropriate "site_handler". For instance, `localhost:8080/youtube.com/...` goes to the `youtube` site handler, whereas `localhost:8080/ytimg.com/...` (the url for video thumbnails) goes to the site handler for just fetching static resources such as images from youtube.

* The reason for this architecture: the original design philosophy when I first conceived the project was that this would work for any site supported by youtube-dl, including Youtube, Vimeo, DailyMotion, etc. I've dropped this idea for now, though I might pick it up later. (youtube-dl is no longer used)

* This file uses the raw [WSGI request](https://www.python.org/dev/peps/pep-3333/) format. The WSGI format is a Python standard for how HTTP servers (I use the stock server provided by gevent) should call HTTP applications. So that's why the file contains stuff like `env['REQUEST_METHOD']`.


## Flask and Gevent
* The `youtube` handler in server.py then delegates the request to the Flask yt_app object, which the rest of the project uses. [Flask](https://flask.palletsprojects.com/en/1.1.x/) is a web application framework that makes handling requests easier than accessing the raw WSGI requests. Flask (Werkzeug specifically) figures out which function to call for a particular url. Each request handling function is registered into Flask's routing table by using function annotations above it. The request handling functions are always at the bottom of the file for a particular youtube page (channel, watch, playlist, etc.), and they're where you want to look to see how the response gets constructed for a particular url. Miscellaneous request handlers that don't belong anywhere else are located in `__init__.py`, which is where the `yt_app` object is instantiated.

* The actual html for youtube-local is generated using Jinja templates. Jinja lets you embed a Python-like language inside html files so you can use constructs such as for loops to construct the html for a list of 30 videos given a dictionary with information for those videos. Jinja is included as part of Flask. It has some annoying differences from Python in a lot of details, so check the [docs here](https://jinja.palletsprojects.com/en/2.11.x/) when you use it. The request handling functions will pass the information that has been scraped from Youtube into these templates for the final result.
* The project uses the gevent library for parallelism (such as for launching requests in parallel), as opposed to using the async keyword.

## util.py
* util.py is a grab-bag of miscellaneous things; admittedly I need to get around to refactoring it. The biggest thing it has is the `fetch_url` function which is what I use for sending out requests for Youtube. The Tor routing is managed here. `fetch_url` will raise an a `FetchError` exception if the request fails. The parameter `debug_name` in `fetch_url` is the filename that the response from Youtube will be saved to if the hidden debugging option is enabled in settings.txt. So if there's a bug when Youtube changes something, you can check the response from Youtube from that file.

## Data extraction - protobuf, polymer, and yt_data_extract
* proto.py is used for generating what are called ctokens needed when making requests to Youtube. These ctokens use Google's [protobuf](https://developers.google.com/protocol-buffers) format. Figuring out how to generate these in new instances requires some reverse engineering. I have a messy python file I use to make this convenient which you can find under ./youtube/proto_debug.py

* The responses from Youtube are in a JSON format called polymer (polymer is the name of the 2017-present Youtube layout). The JSON consists of a bunch of nested dictionaries which basically specify the layout of the page via objects called renderers. A renderer represents an object on a page in a similar way to html tags; the renders often contain renders inside them. The Javascript on Youtube's page translates this JSON to HTML. Example: `compactVideoRenderer` represents a video item in you can click on such as in the related videos (so these are called "items" in the codebase). This JSON is very messy. You'll need a JSON prettifier or something that gives you a tree view in order to study it.

* `yt_data_extract` is a module that parses this this raw JSON page layout and extracts the useful information from it into a standardized dictionary. So for instance, it can take the raw JSON response from the watch page and return a dictionary containing keys such as `title`, `description`,`related_videos (list)`, `likes`, etc. This module contains a lot of abstractions designed to make parsing the polymer format easier and more resilient towards changes from Youtube. (A lot of Youtube extractors just traverse the JSON tree like `response[1]['response']['continuation']['gridContinuationRenderer']['items']...` but this tends to break frequently when Youtube changes things.) If it fails to extract a piece of data, such as the like count, it will place `None` in that entry. Exceptions are not used in this module. So it uses functions which return None if there's a failure, such as `deep_get(response, 1, 'response', 'continuation', 'gridContinuationRenderer', 'items')` which returns None if any of those keys aren't present. The general purpose abstractions are located in `common.py`, while the functions for parsing specific responses (watch page, playlist, channel, etc.) are located in `watch_extraction.py` and `everything_else.py`.

* Most of these abstractions are self-explanatory, except for `extract_items_from_renderer`, a function that performs a recursive search for the specified renderers. You give it a renderer which contains nested renderers, and a set of the renderer types you want to extract (by default, these are the video/playlist/channel preview items). It will search through the nested renderers and gather the specified items, in addition to the continuation token (ctoken) for the last list of items it finds if there is one. Using this function achieves resiliency against Youtube rearranging the items into a different hierarchy.

* The `extract_items` function is similar but works on the response object, automatically finding the appropriate renderer to call `extract_items_from_renderer` on.


## Other
* subscriptions.py uses SQLite to store data.

* Hidden settings only relevant to developers (such as for debugging) are not displayed on the settings page. They can be found in the settings.txt file.

* Since I can't anticipate the things that will trip up beginners to the codebase, if you spend awhile figuring something out, go ahead and make a pull request adding a brief description of your findings to this document to help other beginners.

## Development tips
* When developing functionality to interact with Youtube in new ways, you'll want to use the network tab in your browser's devtools to inspect which requests get made under normal usage of Youtube. You'll also want a tool you can use to construct custom requests and specify headers to reverse engineer the request format. I use the [HeaderTool](https://github.com/loreii/HeaderTool) extension in Firefox, but there's probably a more streamlined program out there.

* You'll want to have a utility or IDE that can perform full text search on a repository, since this is crucial for navigating unfamiliar codebases to figure out where certain strings appear or where things get defined.

* If you're confused what the purpose of a particular line/section of code is, you can use the "git blame" feature on github (click the line number and then the three dots) to view the commit where the line of code was created and check the commit message. This will give you an idea of how it was put together.
