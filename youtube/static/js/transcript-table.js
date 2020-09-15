var details_tt, select_tt, table_tt;

function renderCues() {
  var tt = Q("video").textTracks[select_tt.selectedIndex];
  let cuesL = [...tt.cues];
  var tt_type = cuesL[0].text.startsWith(" \n");
  let ff_bug = false;
  if (!cuesL[0].text.length) { ff_bug = true; tt_type = true };
  let rows;

  function forEachCue(cb) {
    for (let i=0; i < cuesL.length; i++) {
      let txt, startTime = tt.cues[i].startTime;
      if (tt_type) {
        if (i % 2) continue;
        if (ff_bug && !tt.cues[i].text.length) txt = tt.cues[i+1].text;
        else txt = tt.cues[i].text.split('\n')[1].replace(/<[\d:.]*?><c>(.*?)<\/c>/g, "$1");
      } else {
        txt = tt.cues[i].text;
      }
      cb(startTime, txt);
    }
  }

  function createA(startTime, txt, title=null) {
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
  console.log("render cues..", tt.cues.length);
  if (Q("input#transcript-use-table").checked) {
    forEachCue((startTime, txt) => {
      let tr, td, a;
      tr = document.createElement("tr");

      td = document.createElement("td")
      td.appendChild(createA(startTime, toMS(startTime)));
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

      span.appendChild(createA(startTime, firstWord, toMS(startTime)));
      if (rest) span.appendChild(text(rest + " "));
      table_tt.appendChild(span);
    });
    rows = table_tt.childNodes;
  }

  var lastActiveRow = null;
  function colorCurRow(e) {
    // console.log("cuechange:", e);
    var idxC = cuesL.findIndex((c) => c == tt.activeCues[0]);
    var idxT = tt_type ? Math.floor(idxC / 2) : idxC;

    if (lastActiveRow) lastActiveRow.style.backgroundColor = "";
    if (idxT < 0) return;
    var row = rows[idxT];
    row.style.backgroundColor = "#0cc12e42";
    lastActiveRow = row;
  }
  colorCurRow();
  tt.addEventListener("cuechange", colorCurRow);
}

function loadCues() {
  let tts = Q("video").textTracks;
  let tt = tts[select_tt.selectedIndex];
  let dst_mode = "hidden";
  for (let ttI of tts) {
    if (ttI.mode === "showing") dst_mode = "showing";
    if (ttI !== tt) ttI.mode = "disabled";
  }
  if (tt.mode == "disabled") tt.mode = dst_mode;

  var iC = setInterval(() => {
    if (tt.cues && tt.cues.length) {
      clearInterval(iC);
      renderCues();
    }
  }, 100);
}

window.addEventListener('DOMContentLoaded', function() {
  let tts = Q("video").textTracks;
  if (!tts.length) return;

  details_tt = Q("details#transcript-box");
  details_tt.addEventListener("toggle", () => {
    if (details_tt.open) loadCues();
  });

  select_tt = Q("select#select-tt");
  select_tt.selectedIndex = getDefaultTranscriptTrackIdx();
  select_tt.addEventListener("change", loadCues);

  table_tt = Q("table#transcript-table");
  table_tt.appendChild(text("loading.."));

  tts.addEventListener("change", (e) => {
    // console.log(e);
    var idx = getActiveTranscriptTrackIdx();  // sadly not provided by 'e'
    if (tts[idx].mode == "showing") {
      select_tt.selectedIndex = idx;
      loadCues();
    }
    else if (details_tt.open && tts[idx].mode == "disabled") {
      tts[idx].mode = "hidden";  // so we still receive 'oncuechange'
    }
  })

  Q("input#transcript-use-table").addEventListener("change", renderCues);

  Q(".side-videos").prepend(details_tt);
});
