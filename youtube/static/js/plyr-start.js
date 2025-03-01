(function main() {
  'use strict';

  // Captions
  let captionsActive = false;
  if (data.settings.subtitles_mode === 2 || (data.settings.subtitles_mode === 1 && data.has_manual_captions)) {
    captionsActive = true;
  }

  // AutoPlay
  let autoplayActive = data.settings.autoplay_videos || false;

  let qualityOptions = [];
  let qualityDefault;

  for (let src of data.uni_sources) {
    qualityOptions.push(src.quality_string);
  }

  for (let src of data.pair_sources) {
    qualityOptions.push(src.quality_string);
  }

  if (data.using_pair_sources) {
    qualityDefault = data.pair_sources[data.pair_idx].quality_string;
  } else if (data.uni_sources.length !== 0) {
    qualityDefault = data.uni_sources[data.uni_idx].quality_string;
  } else {
    qualityDefault = 'None';
  }

  // Fix plyr refusing to work with qualities that are strings
  Object.defineProperty(Plyr.prototype, 'quality', {
    set: function (input) {
      const config = this.config.quality;
      const options = this.options.quality;
      let quality = input;
      let updateStorage = true;

      if (!options.length) {
        return;
      }

      if (!options.includes(quality)) {
        return;
      }

      // Update config
      config.selected = quality;

      // Set quality
      this.media.quality = quality;

      // Save to storage
      if (updateStorage) {
        this.storage.set({ quality });
      }
    },
  });

  const playerOptions = {
    // Learning about autoplay permission https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy/autoplay#syntax
    autoplay: autoplayActive,
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
      'duration',
      'mute',
      'volume',
      'captions',
      'settings',
      'pip',
      'airplay',
      'fullscreen',
    ],
    iconUrl: '/youtube.com/static/modules/plyr/plyr.svg',
    blankVideo: '/youtube.com/static/modules/plyr/blank.webm',
    debug: false,
    storage: { enabled: false },
    quality: {
      default: qualityDefault,
      options: qualityOptions,
      forced: true,
      onChange: function (quality) {
        if (quality == 'None') {
          return;
        }
        if (quality.includes('(integrated)')) {
          for (let i = 0; i < data.uni_sources.length; i++) {
            if (data.uni_sources[i].quality_string == quality) {
              changeQuality({ type: 'uni', index: i });
              return;
            }
          }
        } else {
          for (let i = 0; i < data.pair_sources.length; i++) {
            if (data.pair_sources[i].quality_string == quality) {
              changeQuality({ type: 'pair', index: i });
              return;
            }
          }
        }
      },
    },
    previewThumbnails: {
      enabled: storyboard_url !== null,
      src: [storyboard_url],
    },
    settings: ['captions', 'quality', 'speed', 'loop'],
    tooltips: {
      controls: true,
    },
  }

  // if the value set by user is -1, the volume option is omitted, as it only accepts value b/w 0 and 1
  // https://github.com/sampotts/plyr#options
  if (data.settings.default_volume !== -1) {
    playerOptions.volume = data.settings.default_volume / 100;
  }

  const player = new Plyr(document.getElementById('js-video-player'), playerOptions);

  // disable double click to fullscreen
  // https://github.com/sampotts/plyr/issues/1370#issuecomment-528966795
  player.eventListeners.forEach(function(eventListener) {
    if(eventListener.type === 'dblclick') {
        eventListener.element.removeEventListener(eventListener.type, eventListener.callback, eventListener.options);
    }
  });

  // Add .started property, true after the playback has been started
  // Needed so controls won't be hidden before playback has started
  player.started = false;
  player.once('playing', function(){this.started = true});
})();
