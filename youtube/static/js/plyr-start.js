var captionsActive;
if(data.settings.subtitles_mode == 2)
    captionsActive = true;
else if(data.settings.subtitles_mode == 1 && data.has_manual_captions)
    captionsActive = true;
else
    captionsActive = false;

const player = new Plyr(document.querySelector('video'), {
    disableContextMenu: false,
    captions: {
        active: captionsActive,
        language: data.settings.subtitles_language,
    },
    controls: [
        'play-large',
        'play',
        'progress',
        'current-time',
        'mute',
        'volume',
        'captions',
        'settings',
        'fullscreen',
    ],
    iconUrl: "/youtube.com/static/modules/plyr/plyr.svg",
    blankVideo: "/youtube.com/static/modules/plyr/blank.webm",
    debug: false,
    storage: {enabled: false},
    // disable plyr hotkeys in favor of hotkeys.js
    keyboard: {
        focused: false,
        global: false,
    },
});

// disable double click to fullscreen
// https://github.com/sampotts/plyr/issues/1370#issuecomment-528966795
player.eventListeners.forEach(function(eventListener) {
    if(eventListener.type === 'dblclick') {
        eventListener.element.removeEventListener(eventListener.type, eventListener.callback, eventListener.options);
    }
});
