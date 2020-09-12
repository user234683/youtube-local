Q = document.querySelector.bind(document);
function text(msg) { return document.createTextNode(msg); }
function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function toMS(s) {
  var s = Math.floor(s);
  var m = Math.floor(s/60); var s = s % 60;
  return `0${m}:`.slice(-3) + `0${s}`.slice(-2);
}


var cur_tt_idx = 0;
function getActiveTranscriptTrackIdx() {
    let tts = Q("video").textTracks;
    if (!tts.length) return;
    for (let i=0; i < tts.length; i++) {
        if (tts[i].mode == "showing") {
            cur_tt_idx = i;
            return cur_tt_idx;
        }
    }
    return cur_tt_idx;
}
function getActiveTranscriptTrack() { return Q("video").textTracks[getActiveTranscriptTrackIdx()]; }

function getDefaultTranscriptTrackIdx() {
  let tts = Q("video").textTracks;
  return tts.length - 1;
}

window.addEventListener('DOMContentLoaded', function() {
    cur_tt_idx = getDefaultTranscriptTrackIdx();
});
