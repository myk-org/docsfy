(function() {
  document.querySelectorAll('pre > code').forEach(function(code) {
    var classes = code.className.split(' ');
    var lang = '';
    classes.forEach(function(cls) {
      if (cls.startsWith('language-')) lang = cls.replace('language-', '');
    });
    if (!lang) {
      // Try highlight.js class pattern
      var highlight = code.closest('.highlight');
      if (highlight) {
        var pre = highlight.querySelector('pre');
        if (pre) {
          var preClasses = pre.className.split(' ');
          preClasses.forEach(function(cls) {
            if (cls.startsWith('language-')) lang = cls.replace('language-', '');
          });
        }
      }
    }
    // Also try codehilite span classes for Pygments
    if (!lang && code.querySelector('.kn, .kd, .k')) {
      // Try to detect from Pygments output
      var parent = code.closest('.highlight, .codehilite');
      if (parent) {
        var divClass = parent.className;
        // Pygments sometimes adds language class to wrapper
        var match = divClass.match(/language-(\w+)/);
        if (match) lang = match[1];
      }
    }
    if (lang) {
      var label = document.createElement('span');
      label.className = 'code-lang-label';
      label.textContent = lang;
      var pre = code.closest('pre');
      if (pre) {
        pre.style.position = 'relative';
        pre.appendChild(label);
      }
    }
  });
})();
