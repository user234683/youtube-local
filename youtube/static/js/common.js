Q = document.querySelector.bind(document);
function text(msg) { return document.createTextNode(msg); }
function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function toTimestamp(seconds) {
  var seconds = Math.floor(seconds);

  var minutes = Math.floor(seconds/60);
  var seconds = seconds % 60;

  var hours = Math.floor(minutes/60);
  var minutes = minutes % 60;

  if (hours) {
    return `0${hours}:`.slice(-3) + `0${minutes}:`.slice(-3) + `0${seconds}`.slice(-2);
  }
  return `0${minutes}:`.slice(-3) + `0${seconds}`.slice(-2);
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
