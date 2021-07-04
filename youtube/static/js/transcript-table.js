var details_tt, select_tt, table_tt;

function renderCues() {
  var selectedTrack = Q("video").textTracks[select_tt.selectedIndex];
  let cuesList = [...selectedTrack.cues];
  var is_automatic = cuesList[0].text.startsWith(" \n");

  // Firefox ignores cues starting with a blank line containing a space
  // Automatic captions contain such a blank line in the first cue
  let ff_bug = false;
  if (!cuesList[0].text.length) { ff_bug = true; is_automatic = true };
  let rows;

  function forEachCue(callback) {
    for (let i=0; i < cuesList.length; i++) {
      let txt, startTime = selectedTrack.cues[i].startTime;
      if (is_automatic) {
        // Automatic captions repeat content. The new segment is displayed
        // on the bottom row; the old one is displayed on the top row.
        // So grab the bottom row only. Skip every other cue because the bottom
        // row is empty.
        if (i % 2) continue;
        if (ff_bug && !selectedTrack.cues[i].text.length) {
          txt = selectedTrack.cues[i+1].text;
        } else {
          txt = selectedTrack.cues[i].text.split('\n')[1].replace(/<[\d:.]*?><c>(.*?)<\/c>/g, "$1");
        }
      } else {
        txt = selectedTrack.cues[i].text;
      }
      callback(startTime, txt);
    }
  }

  function createTimestampLink(startTime, txt, title=null) {
    a = document.createElement("a");
    a.appendChild(text(txt));
    a.href = "javascript:;";  // TODO: replace this with ?t parameter
    if (title) a.title = title;
    a.addEventListener("click", (e) => {
      Q("video").currentTime = startTime;
    })
    return a;
  }

  clearNode(table_tt);
  console.log("render cues..", selectedTrack.cues.length);
  if (Q("input#transcript-use-table").checked) {
    forEachCue((startTime, txt) => {
      let tr, td, a;
      tr = document.createElement("tr");

      td = document.createElement("td")
      td.appendChild(createTimestampLink(startTime, toTimestamp(startTime)));
      tr.appendChild(td);

      td = document.createElement("td")
      td.appendChild(text(txt));
      tr.appendChild(td);

      table_tt.appendChild(tr);
    });
    rows = table_tt.rows;
  }
  else {
    forEachCue((startTime, txt) => {
      span = document.createElement("span");
      var idx = txt.indexOf(" ", 1);
      var [firstWord, rest] = [txt.slice(0, idx), txt.slice(idx)];

      span.appendChild(createTimestampLink(startTime, firstWord, toTimestamp(startTime)));
      if (rest) span.appendChild(text(rest + " "));
      table_tt.appendChild(span);
    });
    rows = table_tt.childNodes;
  }

  var lastActiveRow = null;
  function colorCurRow(e) {
    // console.log("cuechange:", e);
    var activeCueIdx = cuesList.findIndex((c) => c == selectedTrack.activeCues[0]);
    var activeRowIdx = is_automatic ? Math.floor(activeCueIdx / 2) : activeCueIdx;

    if (lastActiveRow) lastActiveRow.style.backgroundColor = "";
    if (activeRowIdx < 0) return;
    var row = rows[activeRowIdx];
    row.style.backgroundColor = "#0cc12e42";
    lastActiveRow = row;
  }
  colorCurRow();
  selectedTrack.addEventListener("cuechange", colorCurRow);
}

function loadCues() {
  let textTracks = Q("video").textTracks;
  let selectedTrack = textTracks[select_tt.selectedIndex];

  // See https://developer.mozilla.org/en-US/docs/Web/API/TextTrack/mode
  // This code will (I think) make sure that the selected track's cues
  // are loaded even if the track subtitles aren't on (showing). Setting it
  // to hidden will load them.
  let selected_track_target_mode = "hidden";

  for (let track of textTracks) {
    // Want to avoid unshowing selected track if it's showing
    if (track.mode === "showing") selected_track_target_mode = "showing";

    if (track !== selectedTrack) track.mode = "disabled";
  }
  if (selectedTrack.mode == "disabled") {
    selectedTrack.mode = selected_track_target_mode;
  }

  var intervalID = setInterval(() => {
    if (selectedTrack.cues && selectedTrack.cues.length) {
      clearInterval(intervalID);
      renderCues();
    }
  }, 100);
}

window.addEventListener('DOMContentLoaded', function() {
  let textTracks = Q("video").textTracks;
  if (!textTracks.length) return;

  details_tt = Q("details#transcript-details");
  details_tt.addEventListener("toggle", () => {
    if (details_tt.open) loadCues();
  });

  select_tt = Q("select#select-tt");
  select_tt.selectedIndex = getDefaultTranscriptTrackIdx();
  select_tt.addEventListener("change", loadCues);

  table_tt = Q("table#transcript-table");
  table_tt.appendChild(text("loading.."));

  textTracks.addEventListener("change", (e) => {
    // console.log(e);
    var idx = getActiveTranscriptTrackIdx();  // sadly not provided by 'e'
    if (textTracks[idx].mode == "showing") {
      select_tt.selectedIndex = idx;
      loadCues();
    }
    else if (details_tt.open && textTracks[idx].mode == "disabled") {
      textTracks[idx].mode = "hidden";  // so we still receive 'oncuechange'
    }
  })

  Q("input#transcript-use-table").addEventListener("change", renderCues);
});
