function onClickReplies(e) {
  let details = e.target.parentElement;
  // e.preventDefault();
  console.log("loading replies ..");
  doXhr(details.getAttribute("data-src") + "&slim=1", (html) => {
    let div = details.querySelector(".comment_page");
    div.innerHTML = html;
  });
  details.removeEventListener('click', onClickReplies);
}

window.addEventListener('DOMContentLoaded', function() {
    QA("details.replies").forEach(details => {
      details.addEventListener('click', onClickReplies);
      details.addEventListener('auxclick', (e) => {
        if (e.target.parentElement !== details) return;
        if (e.button == 1) window.open(details.getAttribute("data-src"));
      });
    });
});
