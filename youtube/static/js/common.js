Q = document.querySelector.bind(document);
function text(msg) { return document.createTextNode(msg); }
function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function toTimestamp(s) {
  var s = Math.floor(s);
  var m = Math.floor(s/60); var s = s % 60;
  return `0${m}:`.slice(-3) + `0${s}`.slice(-2);
}


var cur_track_idx = 0;
function getActiveTranscriptTrackIdx() {
    let textTracks = Q("video").textTracks;
    if (!textTracks.length) return;
    for (let i=0; i < textTracks.length; i++) {
        if (textTracks[i].mode == "showing") {
            cur_track_idx = i;
            return cur_track_idx;
        }
    }
    return cur_track_idx;
}
function getActiveTranscriptTrack() { return Q("video").textTracks[getActiveTranscriptTrackIdx()]; }

function getDefaultTranscriptTrackIdx() {
  let textTracks = Q("video").textTracks;
  return textTracks.length - 1;
}

window.addEventListener('DOMContentLoaded', function() {
    cur_track_idx = getDefaultTranscriptTrackIdx();
});
