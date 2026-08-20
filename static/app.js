// ========================================================
// Global SmartAttend UI helpers
// ========================================================

function toggleSidebar() {
    // The mobile menu simply adds/removes a CSS class.
    document.getElementById('sidebar')?.classList.toggle('open');
}

function toggleTheme() {
    // Save the user's choice so it survives a page refresh.
    const root = document.documentElement;
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    localStorage.setItem('smartattend-theme', next);
}

// Restore the saved theme when the page loads.
(function restoreTheme() {
    const saved = localStorage.getItem('smartattend-theme');
    if (saved) document.documentElement.dataset.theme = saved;
})();

// Small toast animation: remove old notifications automatically.
setTimeout(() => {
    document.querySelectorAll('.toast').forEach(toast => {
        toast.classList.add('hide');
    });
}, 4500);
