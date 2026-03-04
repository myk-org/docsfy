(function() {
  document.querySelectorAll('blockquote').forEach(function(bq) {
    var strong = bq.querySelector('p:first-child > strong:first-child');
    if (!strong) return;
    var text = strong.textContent.toLowerCase();
    if (text.startsWith('note')) bq.classList.add('callout-note');
    else if (text.startsWith('warning')) bq.classList.add('callout-warning');
    else if (text.startsWith('tip')) bq.classList.add('callout-tip');
    else if (text.startsWith('info')) bq.classList.add('callout-note');
  });
})();
