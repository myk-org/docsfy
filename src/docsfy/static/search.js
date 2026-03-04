(function() {
  var input = document.getElementById('search-input');
  var results = document.getElementById('search-results');
  if (!input || !results) return;
  var index = [];
  fetch('search-index.json')
    .then(function(r) { return r.json(); })
    .then(function(data) { index = data; })
    .catch(function() {});

  function clearResults() {
    while (results.firstChild) {
      results.removeChild(results.firstChild);
    }
  }

  input.addEventListener('input', function() {
    var q = this.value.toLowerCase().trim();
    clearResults();
    if (!q) { results.style.display = 'none'; return; }
    var matches = index.filter(function(item) {
      return item.title.toLowerCase().includes(q) || item.content.toLowerCase().includes(q);
    });
    if (matches.length === 0) { results.style.display = 'none'; return; }
    results.style.display = 'block';
    matches.forEach(function(m) {
      var a = document.createElement('a');
      a.href = m.slug + '.html';
      a.textContent = m.title;
      a.className = 'search-result-item';
      results.appendChild(a);
    });
  });
  document.addEventListener('click', function(e) {
    if (!results.contains(e.target) && e.target !== input) {
      results.style.display = 'none';
    }
  });
})();
