function onKeyDown(e) {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return false;

    // console.log(e);
    let v = QId("js-video-player");
    if (!e.isTrusted) return;  // plyr CustomEvent
    let c = e.key.toLowerCase();
    if (e.ctrlKey) return;
    else if (c == "k") {
        v.paused ? v.play() : v.pause();
    }
    else if (c == "arrowleft") {
        e.preventDefault();
        v.currentTime = v.currentTime - 5;
    }
    else if (c == "arrowright") {
        e.preventDefault();
        v.currentTime = v.currentTime + 5;
    }
    else if (c == "j") {
        e.preventDefault();
        v.currentTime = v.currentTime - 10;
    }
    else if (c == "l") {
        e.preventDefault();
        v.currentTime = v.currentTime + 10;
    }
    else if (c == "f") {
        e.preventDefault();
        if (data.settings.use_video_player == 2) {
            player.fullscreen.toggle()
        }
        else {
            if (document.fullscreen) {
                document.exitFullscreen()
            }
            else {
                v.requestFullscreen()
            }
        }
    }
    else if (c == "m") {
        if (v.muted == false) {v.muted = true;}
        else {v.muted = false;}
    }
    else if (c == "c") {
        e.preventDefault();
        let tt = getActiveTranscriptTrack();
        if (tt == null) return;
        if (tt.mode == "showing") tt.mode = "disabled";
        else tt.mode = "showing";
    }
    else if (c == "t") {
        let ts = Math.floor(QId("js-video-player").currentTime);
        copyTextToClipboard(`https://youtu.be/${data.video_id}?t=${ts}`);
    }
}

window.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('keydown', onKeyDown);
});
