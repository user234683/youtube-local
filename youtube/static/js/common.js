const Q = document.querySelector.bind(document);
const QA = document.querySelectorAll.bind(document);
const QId = document.getElementById.bind(document);
let seconds,
    minutes,
    hours;
function text(msg) { return document.createTextNode(msg); }
function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function toTimestamp(seconds) {
  seconds = Math.floor(seconds);

  minutes = Math.floor(seconds/60);
  seconds = seconds % 60;

  hours = Math.floor(minutes/60);
  minutes = minutes % 60;

  if (hours) {
    return `0${hours}:`.slice(-3) + `0${minutes}:`.slice(-3) + `0${seconds}`.slice(-2);
  }
  return `0${minutes}:`.slice(-3) + `0${seconds}`.slice(-2);
}

let cur_track_idx = 0;
function getActiveTranscriptTrackIdx() {
    let textTracks = QId("js-video-player").textTracks;
    if (!textTracks.length) return;
    for (let i=0; i < textTracks.length; i++) {
        if (textTracks[i].mode == "showing") {
            cur_track_idx = i;
            return cur_track_idx;
        }
    }
    return cur_track_idx;
}
function getActiveTranscriptTrack() { return QId("js-video-player").textTracks[getActiveTranscriptTrackIdx()]; }

function getDefaultTranscriptTrackIdx() {
  let textTracks = QId("js-video-player").textTracks;
  return textTracks.length - 1;
}

function doXhr(url, callback=null) {
    let xhr = new XMLHttpRequest();
    xhr.open("GET", url);
    xhr.onload = (e) => {
      callback(e.currentTarget.response);
    }
    xhr.send();
    return xhr;
}

// https://stackoverflow.com/a/30810322
function copyTextToClipboard(text) {
  let textArea = document.createElement("textarea");

  //
  // *** This styling is an extra step which is likely not required. ***
  //
  // Why is it here? To ensure:
  // 1. the element is able to have focus and selection.
  // 2. if element was to flash render it has minimal visual impact.
  // 3. less flakyness with selection and copying which **might** occur if
  //    the textarea element is not visible.
  //
  // The likelihood is the element won't even render, not even a
  // flash, so some of these are just precautions. However in
  // Internet Explorer the element is visible whilst the popup
  // box asking the user for permission for the web page to
  // copy to the clipboard.
  //

  // Place in top-left corner of screen regardless of scroll position.
  textArea.style.position = 'fixed';
  textArea.style.top = 0;
  textArea.style.left = 0;

  // Ensure it has a small width and height. Setting to 1px / 1em
  // doesn't work as this gives a negative w/h on some browsers.
  textArea.style.width = '2em';
  textArea.style.height = '2em';

  // We don't need padding, reducing the size if it does flash render.
  textArea.style.padding = 0;

  // Clean up any borders.
  textArea.style.border = 'none';
  textArea.style.outline = 'none';
  textArea.style.boxShadow = 'none';

  // Avoid flash of white box if rendered for any reason.
  textArea.style.background = 'transparent';


  textArea.value = text;

  let parent_el = video.parentElement;
  parent_el.appendChild(textArea);
  textArea.focus();
  textArea.select();

  try {
    let successful = document.execCommand('copy');
    let msg = successful ? 'successful' : 'unsuccessful';
    console.log('Copying text command was ' + msg);
  } catch (err) {
    console.log('Oops, unable to copy');
  }

  parent_el.removeChild(textArea);
}


window.addEventListener('DOMContentLoaded', function() {
    cur_track_idx = getDefaultTranscriptTrackIdx();
});
