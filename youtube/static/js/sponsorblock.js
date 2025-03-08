"use strict";

// from: https://git.gir.st/subscriptionfeed.git/blob/59a590d:/app/youtube/templates/watch.html.j2#l28

let sha256=function a(b){function c(a,b){return a>>>b|a<<32-b}for(var d,e,f=Math.pow,g=f(2,32),h="length",i="",j=[],k=8*b[h],l=a.h=a.h||[],m=a.k=a.k||[],n=m[h],o={},p=2;64>n;p++)if(!o[p]){for(d=0;313>d;d+=p)o[d]=p;l[n]=f(p,.5)*g|0,m[n++]=f(p,1/3)*g|0}for(b+="\x80";b[h]%64-56;)b+="\x00";for(d=0;d<b[h];d++){if(e=b.charCodeAt(d),e>>8)return;j[d>>2]|=e<<(3-d)%4*8}for(j[j[h]]=k/g|0,j[j[h]]=k,e=0;e<j[h];){var q=j.slice(e,e+=16),r=l;for(l=l.slice(0,8),d=0;64>d;d++){var s=q[d-15],t=q[d-2],u=l[0],v=l[4],w=l[7]+(c(v,6)^c(v,11)^c(v,25))+(v&l[5]^~v&l[6])+m[d]+(q[d]=16>d?q[d]:q[d-16]+(c(s,7)^c(s,18)^s>>>3)+q[d-7]+(c(t,17)^c(t,19)^t>>>10)|0),x=(c(u,2)^c(u,13)^c(u,22))+(u&l[1]^u&l[2]^l[1]&l[2]);l=[w+x|0].concat(l),l[4]=l[4]+w|0}for(d=0;8>d;d++)l[d]=l[d]+r[d]|0}for(d=0;8>d;d++)for(e=3;e+1;e--){var y=l[d]>>8*e&255;i+=(16>y?0:"")+y.toString(16)}return i}; /*https://geraintluff.github.io/sha256/sha256.min.js (public domain)*/

window.addEventListener("load", load_sponsorblock);
document.addEventListener('DOMContentLoaded', ()=>{
  const check = document.querySelector("#skip_sponsors");
  check.addEventListener("change", () => {if (check.checked) load_sponsorblock()});
});
function load_sponsorblock(){
  const info_elem = Q('#skip_n');
  if (info_elem.innerText.length) return;  // already fetched
  const hash = sha256(data.video_id).substr(0,4);
  const video_obj = QId("js-video-player");
  let url = `/https://sponsor.ajay.app/api/skipSegments/${hash}`;
  fetch(url)
      .then(response => response.json())
      .then(r => {
    for (const video of r) {
      if (video.videoID != data.video_id) continue;
      info_elem.innerText = `(${video.segments.length} segments)`;
      const cat_n = video.segments.map(e=>e.category).sort()
          .reduce((acc,e) => (acc[e]=(acc[e]||0)+1, acc), {});
      info_elem.title = Object.entries(cat_n).map(e=>e.join(': ')).join(', ');
      for (const segment of video.segments) {
        const [start, stop] = segment.segment;
        if (segment.category != "sponsor") continue;
        video_obj.addEventListener("timeupdate", function() {
          if (Q("#skip_sponsors").checked &&
              this.currentTime >= start &&
              this.currentTime < stop-1) {
            this.currentTime = stop;
          }
        });
      }
    }
  });
}
