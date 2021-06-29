var options = {
	preload: 'auto',
	liveui: true,
	playbackRates: [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
	controlBar: {
		children: [
			'playToggle',
			'volumePanel',
			'currentTimeDisplay',
			'timeDivider',
			'durationDisplay',
			'progressControl',
			'remainingTimeDisplay',
			'Spacer',
			'captionsButton',
			'qualitySelector',
			'playbackRateMenuButton',
			'fullscreenToggle'
		]
	},
	html5: {
		preloadTextTracks: false,
		hls: {
			overrideNative: true
		}
	}
}

function makeAudioSynced(video, audio) {
	// from: https://git.sr.ht/~cadence/cloudtube/tree/eb111a44/item/html/static/js/player.js#L63

	function playbackIntervention(event) {
		// console.log(event.target.tagName.toLowerCase(), event.type)
		let target = event.target
		let other = (event.target === video ? audio : video)
		switch (event.type) {
		/* video only */
		case "pause":
			other.pause();
			other.currentTime = target.currentTime;
			break;
		case "play":
			other.currentTime = target.currentTime;
			other.play();
			break;
		case "playing":
			other.currentTime = target.currentTime;
			if (audio.paused) audio.play();
			break;
		case "seeking":
			audio.pause();
		case "seeked":
			target.ready = false;
			other.ready = false;
			audio.play();
			other.currentTime = target.currentTime;
			break;
		case "ratechange":
			other.playbackRate = target.playbackRate;
			break;
		case "volumechange":
			console.log(target);
			other.volume = target.volume;
			break;

		/* both */
		case "canplaythrough":
			if (!target.ready && !video.paused) {
				target.ready = true;
				if (other.ready) {
					// target.play();
					other.play();
				}
			}
			break;
		// case "stalled":
		case "waiting":  // TODO: handle waiting for audio
			if (target === video) {
				video.ready = false;
				audio.pause();
				break;
			}
		}
	}

	for (let eventName of ["pause", "play", "playing", "seeked", "seeking", "ratechange", "volumechange"]) {
		video.addEventListener(eventName, playbackIntervention)
	}
	for (let eventName of ["canplaythrough", "waiting", "stalled"]) {
		video.addEventListener(eventName, playbackIntervention)
		audio.addEventListener(eventName, playbackIntervention)
	}
}

function makeVolumeScrollable(player) {
	function increase_volume(delta) {
    const curVolume = player.volume();
    let newVolume = curVolume + delta;
    if (newVolume > 1) {
        newVolume = 1;
    } else if (newVolume < 0) {
        newVolume = 0;
    }
    player.volume(newVolume);
	}

	// Add support for controlling the player volume by scrolling over it. Adapted from
	// https://github.com/ctd1500/videojs-hotkeys/blob/bb4a158b2e214ccab87c2e7b95f42bc45c6bfd87/videojs.hotkeys.js#L292-L328
	(function () {
		const volumeStep = 0.05;
		const enableVolumeScroll = true;
		const enableHoverScroll = true;
		const doc = document;
		const pEl = document.getElementById('player');

		var volumeHover = false;
		var volumeSelector = pEl.querySelector('.vjs-volume-menu-button') || pEl.querySelector('.vjs-volume-panel');
		if (volumeSelector != null) {
			volumeSelector.onmouseover = function () { volumeHover = true; };
			volumeSelector.onmouseout = function () { volumeHover = false; };
		}

		var mouseScroll = function mouseScroll(event) {
			var activeEl = doc.activeElement;
			if (enableHoverScroll) {
				// If we leave this undefined then it can match non-existent elements below
				activeEl = 0;
			}

			// When controls are disabled, hotkeys will be disabled as well
			if (player.controls()) {
				if (volumeHover) {
					if (enableVolumeScroll) {
						event = window.event || event;
						var delta = Math.max(-1, Math.min(1, (event.wheelDelta || -event.detail)));
						event.preventDefault();

						if (delta == 1) {
							increase_volume(volumeStep);
						} else if (delta == -1) {
							increase_volume(-volumeStep);
						}
					}
				}
			}
		};

		player.on('mousewheel', mouseScroll);
		player.on("DOMMouseScroll", mouseScroll);
	}());
}

window.addEventListener('DOMContentLoaded', function() {
	let v = Q("video");

	var player = videojs(v, options);
	window.player = player;

	makeVolumeScrollable(player);

	let l = [];
	for (let e of download_formats) {
		if (e.audio_quality != "video only") continue;

		// if (!e.codecs.startsWith("avc1")) continue;  // ff: avc1+av1 seek induces >5min loading, vp9 is ok
		if (!e.codecs.startsWith("vp9")) continue;

		let label = e.video_quality.match(/\d+x(.*)/)[1].replace(' ', 'p ');  // 640x360 30fps -> 360p 30fps
		let q = Number.parseInt(label.match(/(\d+)/)[1]);
		if (q <= 144 || q > window.screen.height) continue;

		l.push({
			src: e.url,
			type: `video/${e.ext}`,
			label: label,
			// selected: label.startsWith("720p"),
			selected: label.startsWith("1080p"),
		})
	}
	player.src(l);


	function getBestAudio() {
		return download_formats.reduce((acc, e, ) => {
			if (e.video_quality !== "audio only") return acc;
			e.audio_q = Number.parseInt((e.audio_quality.match(/^(\d+)/) || [null])[1]);
			if (isNaN(e.audio_q)) return acc;
			if (!acc) return e;
			if (e.audio_q > acc.audio_q) return e;
			return acc;
		}, null);
	}

	audio_url = getBestAudio().url;
	audio = Q("#audio-el");
	audio.src = audio_url;
	makeAudioSynced(v, audio);
});