const video = document.getElementById('js-video-player');

// if the value set by user is -1, the volume option is omitted, as it only accepts value b/w 0 and 1
// https://github.com/sampotts/plyr#options
if (data.settings.default_volume !== -1) {
    video.volume = data.settings.default_volume / 100;
}

function changeQuality(selection) {
    let currentVideoTime = video.currentTime;
    let videoPaused = video.paused;
    let videoSpeed = video.playbackRate;
    let srcInfo;
    if (avMerge)
        avMerge.close();
    if (selection.type == 'uni'){
        srcInfo = data['uni_sources'][selection.index];
        video.src = srcInfo.url;
    } else {
        srcInfo = data['pair_sources'][selection.index];
        avMerge = new AVMerge(video, srcInfo, currentVideoTime);
    }
    video.currentTime = currentVideoTime;
    if (!videoPaused){
        video.play();
    }
    video.playbackRate = videoSpeed;
}

// Initialize av-merge
let avMerge;
if (data.using_pair_sources) {
    let srcPair = data['pair_sources'][data['pair_idx']];
    // Do it dynamically rather than as the default in jinja
    // in case javascript is disabled
    avMerge = new AVMerge(video, srcPair, 0);
}

// Quality selector
const qs = document.getElementById('quality-select');
if (qs) {
  qs.addEventListener('change', function(e) {
    changeQuality(JSON.parse(this.value))
  });
}

// Set up video start time from &t parameter
if (data.time_start != 0 && video) {video.currentTime = data.time_start};

// External video speed control
let speedInput = document.getElementById('speed-control');
speedInput.addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
        let speed = parseFloat(speedInput.value);
        if(!isNaN(speed)){
            video.playbackRate = speed;
        }
    }
});


// Playlist lazy image loading
if (data.playlist && data.playlist['id'] !== null) {
    // lazy load playlist images
    // copied almost verbatim from
    // https://css-tricks.com/tips-for-rolling-your-own-lazy-loading/
    // IntersectionObserver isn't supported in pre-quantum
    // firefox versions, but the alternative of making it
    // manually is a performance drain, so oh well
    let observer = new IntersectionObserver(lazyLoad, {

      // where in relation to the edge of the viewport, we are observing
      rootMargin: "100px",

      // how much of the element needs to have intersected
      // in order to fire our loading function
      threshold: 1.0

    });

    function lazyLoad(elements) {
      elements.forEach(item => {
        if (item.intersectionRatio > 0) {

          // set the src attribute to trigger a load
          item.target.src = item.target.dataset.src;

          // stop observing this element. Our work here is done!
          observer.unobserve(item.target);
        };
      });
    };

    // Tell our observer to observe all img elements with a "lazy" class
    let lazyImages = document.querySelectorAll('img.lazy');
    lazyImages.forEach(img => {
      observer.observe(img);
    });
}


// Autoplay
if (data.settings.related_videos_mode !== 0 || data.playlist !== null) {
    let playability_error = !!data.playability_error;
    let isPlaylist = false;
    if (data.playlist !== null && data.playlist['current_index'] !== null)
        isPlaylist = true;

    // read cookies on whether to autoplay
    // https://developer.mozilla.org/en-US/docs/Web/API/Document/cookie
    let cookieValue;
    let playlist_id;
    if (isPlaylist) {
        // from https://stackoverflow.com/a/6969486
        function escapeRegExp(string) {
            // $& means the whole matched string
            return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }
        playlist_id = data.playlist['id'];
        playlist_id = escapeRegExp(playlist_id);

        cookieValue = document.cookie.replace(new RegExp(
            '(?:(?:^|.*;\\s*)autoplay_'
            + playlist_id + '\\s*\\=\\s*([^;]*).*$)|^.*$'
        ), '$1');
    } else {
        cookieValue = document.cookie.replace(new RegExp(
            '(?:(?:^|.*;\\s*)autoplay\\s*\\=\\s*([^;]*).*$)|^.*$'
        ),'$1');
    }

    let autoplayEnabled = 0;
    if(cookieValue.length === 0){
        autoplayEnabled = 0;
    } else {
        autoplayEnabled = Number(cookieValue);
    }

    // check the checkbox if autoplay is on
    let checkbox = document.querySelector('.autoplay-toggle');
    if(autoplayEnabled){
        checkbox.checked = true;
    }

    // listen for checkbox to turn autoplay on and off
    let cookie = 'autoplay'
    if (isPlaylist)
        cookie += '_' + playlist_id;

    checkbox.addEventListener( 'change', function() {
        if(this.checked) {
            autoplayEnabled = 1;
            document.cookie = cookie + '=1; SameSite=Strict';
        } else {
            autoplayEnabled = 0;
            document.cookie = cookie + '=0; SameSite=Strict';
        }
    });

    if(!playability_error){
        // play the video if autoplay is on
        if(autoplayEnabled){
            video.play();
        }
    }

    // determine next video url
    let nextVideoUrl;
    if (isPlaylist) {
        let currentIndex = data.playlist['current_index'];
        if (data.playlist['current_index']+1 == data.playlist['items'].length)
            nextVideoUrl = null;
        else
            nextVideoUrl = data.playlist['items'][data.playlist['current_index']+1]['url'];

        // scroll playlist to proper position
        // item height + gap == 100
        let pl = document.querySelector('.playlist-videos');
        pl.scrollTop = 100*currentIndex;
    } else {
        if (data.related.length === 0)
            nextVideoUrl = null;
        else
            nextVideoUrl = data.related[0]['url'];
    }
    let nextVideoDelay = 1000;

    // go to next video when video ends
    // https://stackoverflow.com/a/2880950
    if (nextVideoUrl) {
        if(playability_error){
            videoEnded();
        } else {
            video.addEventListener('ended', videoEnded, false);
        }
        function nextVideo(){
            if(autoplayEnabled){
                window.location.href = nextVideoUrl;
            }
        }
        function videoEnded(e) {
            window.setTimeout(nextVideo, nextVideoDelay);
        }
    }
}
