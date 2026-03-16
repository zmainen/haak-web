const btn = document.getElementById('theme-toggle');
const html = document.documentElement;

function applyTheme(light) {
  if (light) {
    html.setAttribute('data-theme', 'light');
    btn.textContent = 'night';
  } else {
    html.removeAttribute('data-theme');
    btn.textContent = 'day';
  }
  localStorage.setItem('haak-theme', light ? 'light' : 'dark');
}

const saved = localStorage.getItem('haak-theme');
if (saved === 'light') applyTheme(true);

btn.addEventListener('click', () => {
  applyTheme(html.getAttribute('data-theme') !== 'light');
});
