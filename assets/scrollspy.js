(function() {
  var tocLinks = document.querySelectorAll('.toc-container a');
  if (!tocLinks.length) return;

  var headings = [];
  tocLinks.forEach(function(link) {
    var id = link.getAttribute('href');
    if (id && id.startsWith('#')) {
      var el = document.getElementById(id.substring(1));
      if (el) headings.push({ el: el, link: link });
    }
  });

  function onScroll() {
    var scrollY = window.scrollY + 100;
    var current = null;
    headings.forEach(function(h) {
      if (h.el.offsetTop <= scrollY) current = h;
    });
    tocLinks.forEach(function(link) { link.classList.remove('toc-active'); });
    if (current) current.link.classList.add('toc-active');
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
