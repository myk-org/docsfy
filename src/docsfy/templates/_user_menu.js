<script>
function closeUserMenu() {
    var dropdown = document.getElementById('user-menu-dropdown');
    var toggle = document.getElementById('user-menu-toggle');
    if (dropdown) dropdown.classList.remove('open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
}
(function() {
    var toggle = document.getElementById('user-menu-toggle');
    var dropdown = document.getElementById('user-menu-dropdown');
    if (!toggle || !dropdown) return;
    toggle.addEventListener('click', function(e) {
        e.stopPropagation();
        var isOpen = dropdown.classList.contains('open');
        if (isOpen) { closeUserMenu(); } else {
            dropdown.classList.add('open');
            toggle.setAttribute('aria-expanded', 'true');
        }
    });
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#user-menu')) closeUserMenu();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && dropdown.classList.contains('open')) {
            closeUserMenu();
            toggle.focus();
        }
    });
})();
</script>
