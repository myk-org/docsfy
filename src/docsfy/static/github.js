(function() {
  var link = document.getElementById('github-link');
  if (!link) return;
  var url = link.getAttribute('data-repo-url');
  if (!url) return;

  // Extract owner/repo from URL
  var match = url.match(/github\.com\/([^\/]+)\/([^\/\.]+)/);
  if (!match) return;
  var owner = match[1];
  var repo = match[2];

  fetch('https://api.github.com/repos/' + owner + '/' + repo)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var stars = document.getElementById('github-stars');
      if (stars && data.stargazers_count !== undefined) {
        var count = data.stargazers_count;
        if (count >= 1000) {
          stars.textContent = (count / 1000).toFixed(1) + 'k';
        } else {
          stars.textContent = count.toString();
        }
      }
    })
    .catch(function() {});
})();
