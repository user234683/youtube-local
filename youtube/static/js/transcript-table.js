var details_tt, select_tt, table_tt;

function renderCues() {
  var tt = Q("video").textTracks[select_tt.selectedIndex];
  let cuesL = [...tt.cues];

  clearNode(table_tt);
  console.log("render cues..", tt.cues.length);

  var tt_type = cuesL[0].text.startsWith(" \n");
  for (let i=0; i < cuesL.length; i++) {
    let txt, startTime = tt.cues[i].startTime;
    if (tt_type) {
      if (i % 2) continue;
      txt = tt.cues[i].text.split('\n')[1].replace(/<[\d:.]*?><c>(.*?)<\/c>/g, "$1");
    } else {
      txt = tt.cues[i].text;
    }

    let tr, td, a;
    tr = document.createElement("tr");

    td = document.createElement("td")
    a = document.createElement("a");
    a.appendChild(text(toMS(startTime)));
    a.href = "javascript:;";  // TODO: replace this with ?t parameter
    a.addEventListener("click", (e) => {
      Q("video").currentTime = startTime;
    })
    td.appendChild(a);
    tr.appendChild(td);

    td = document.createElement("td")
    td.appendChild(text(txt));
    tr.appendChild(td);

    table_tt.appendChild(tr);;
  };

  var lastActiveRow = null;
  function colorCurRow(e) {
    // console.log("cuechange:", e);
    var idxC = cuesL.findIndex((c) => c == tt.activeCues[0]);
    var idxT = tt_type ? Math.floor(idxC / 2) : idxC;

    if (lastActiveRow) lastActiveRow.style.backgroundColor = "";
    if (idxT < 0) return;
    var row = table_tt.rows[idxT];
    row.style.backgroundColor = "#0cc12e42";
    lastActiveRow = row;
  }
  colorCurRow();
  tt.addEventListener("cuechange", colorCurRow);
}

function loadCues() {
  let tts = Q("video").textTracks;
  let tt = tts[select_tt.selectedIndex];
  for (let ttI of tts) if (ttI !== tt) ttI.mode = "disabled";
  if (tt.mode == "disabled") tt.mode = "hidden";

  var iC = setInterval(() => {
    if (tt.cues && tt.cues.length) {
      renderCues();
      clearInterval(iC);
    }
  }, 100);
}

window.addEventListener('DOMContentLoaded', function() {
  let tts = Q("video").textTracks;
  if (!tts.length) return;

  details_tt = document.createElement("details");
  details_tt.addEventListener("toggle", () => {
    if (details_tt.open) loadCues();
  });

  var s = document.createElement("summary");
  s.appendChild(text("Transcript"));
  details_tt.appendChild(s);

  var divR = document.createElement("div");
  select_tt = document.createElement("select");
  for (let tt of tts) {
    let option = document.createElement("option");
    option.appendChild(text(tt.label));
    select_tt.appendChild(option);
  }
  select_tt.addEventListener("change", loadCues);
  divR.appendChild(select_tt);

  table_tt = document.createElement("table");
  table_tt.id = "transcript-table";
  table_tt.appendChild(text("loading.."));
  divR.appendChild(table_tt);

  tts.addEventListener("change", (e) => {
    console.log(e);
    var idx = getActiveTranscriptTrackIdx();  // sadly not provided by 'e'
    if (tts[idx].mode == "showing") {
      select_tt.selectedIndex = idx;
      loadCues();
    }
    else if (details_tt.open && tts[idx].mode == "disabled") {
      tts[idx].mode = "hidden";  // so we still receive 'oncuechange'
    }
  })

  details_tt.appendChild(divR);
  Q(".side-videos").prepend(details_tt);
});
