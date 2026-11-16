// Общая часть виджетов. Раз в 2 секунды читает:
//   theme.json   - цвета темы (пишет ryoku.py)
//   widgets.json - настройки виджетов (пишет панель «Виджеты»)
// Имя виджета берётся из <body data-widget="clock" data-w="1100">.
const me = document.body.dataset.widget;
let lastTheme = '', lastCfg = '';
export let config = {};
export let tools = null;          // чем запускать скрипты: { program, drag, tasks, audio }
let locked = false;

let zebarLib = null;
export async function exec(args) {
  if (!tools) return;
  zebarLib = zebarLib || await import('./zebar.mjs');
  return zebarLib.shellExec(tools.program, args);
}

// Выделение виджета. Клик по виджету запускает drag.pyw: пока он работает, виджет выделен
// (окантовка, квадратик размера и шестерёнка), а сам скрипт двигает окно, меняет его размер
// и открывает настройки по шестерёнке. Скрипт завершается, когда кликнули мимо виджета
// или нажали Esc, и выделение снимается.
// Элементы с классом .click (кнопки, строки задач) выделение не запускают.
let selected = false;
document.addEventListener('mousedown', async e => {
  if (e.button !== 0 || locked || !tools || selected) return;
  if (e.target.closest('button, .click')) return;
  selected = true;
  document.documentElement.classList.add('selected');
  // где в виджете кнопки, ползунки и строки задач: там нажатие окно не двигает
  const W = window.innerWidth, H = window.innerHeight;
  const zones = [...document.querySelectorAll('button, .click')].map(el => {
    const r = el.getBoundingClientRect();
    return [r.left / W, r.top / H, r.right / W, r.bottom / H].map(v => v.toFixed(4)).join(',');
  }).join(';');
  try { await exec([tools.drag, me, zones || '-']); } catch (err) { console.error('drag', err); }
  selected = false;
  document.documentElement.classList.remove('selected');
});
export function isSelected() { return selected; }

// Окантовка, квадратик размера и шестерёнка. Лежат вне body, чтобы на них не действовал масштаб.
for (const [cls, text] of [['frame', ''], ['grip', ''], ['gear', '']]) {
  const el = document.createElement('div');
  el.className = cls;
  el.textContent = text;
  document.documentElement.appendChild(el);
}

// Масштаб считается от ширины окна: окно растягивают (мышкой или ползунком) - содержимое растёт вместе с ним.
let baseW = +document.body.dataset.w + 4;
export function setBase(w) { if (w + 4 !== baseW) { baseW = w + 4; fit(); } }   // у часов ширина зависит от вида
function fit() { document.body.style.zoom = Math.max(0.2, window.innerWidth / baseW); }
window.addEventListener('resize', fit);
fit();

export async function read(file) {
  const r = await fetch('./' + file + '?t=' + Date.now(), { cache: 'no-store' });
  return r.ok ? r.text() : '';
}

async function poll() {
  try {
    const txt = await read('theme.json');
    if (txt && txt !== lastTheme) {
      lastTheme = txt;
      const t = JSON.parse(txt);
      for (const k of ['fg', 'muted', 'accent', 'accent2', 'accent3', 'glow', 'pill', 'line', 'glass', 'edge']) {
        if (t[k]) document.documentElement.style.setProperty('--' + k, t[k]);
      }
      if (t.wall) document.documentElement.style.setProperty('--wall-img', "url('./" + t.wall + '?v=' + (t.wallv || 0) + "')");
      if (t.screen) screenSize = t.screen;
      document.dispatchEvent(new CustomEvent('theme', { detail: t }));
    }
  } catch (e) {}
  try {
    const txt = await read('widgets.json');
    if (txt && txt !== lastCfg) {
      lastCfg = txt;
      const all = JSON.parse(txt);
      config = all[me] || {};
      tools = all._tools || null;
      locked = !!(all.all && all.all.lock);
      document.body.style.cursor = locked ? 'default' : 'grab';
      document.documentElement.style.setProperty('--opacity', (config.opacity ?? 100) / 100);
      document.dispatchEvent(new CustomEvent('config', { detail: config }));
    }
  } catch (e) {}
}
poll();
setInterval(poll, 2000);

// Стекло: размытые обои внутри карточек должны совпадать с настоящими обоями за окном.
// Для этого фон каждой карточки сдвигается на положение окна на экране и самой карточки в окне.
let screenSize = [screen.width, screen.height], glassKey = '';
function glassTick() {
  const z = parseFloat(document.body.style.zoom) || 1;
  const key = [window.screenX, window.screenY, z, screenSize[0], document.querySelectorAll('.card-bg').length].join();
  if (key === glassKey) return;
  glassKey = key;
  for (const el of document.querySelectorAll('.card-bg')) {
    let x = 0, y = 0;
    for (let e = el; e; e = e.offsetParent) { x += e.offsetLeft; y += e.offsetTop; }
    el.style.setProperty('--wall-x', -(window.screenX / z + x) + 'px');
    el.style.setProperty('--wall-y', -(window.screenY / z + y) + 'px');
    el.style.setProperty('--wall-size', (screenSize[0] / z) + 'px ' + (screenSize[1] / z) + 'px');
  }
}
setInterval(glassTick, 150);

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Показать или скрыть элемент по id.
export function show(id, on) {
  const el = document.getElementById(id);
  if (el) el.style.display = on === false ? 'none' : '';
}

// Размер: 1536 -> "1.5 KiB"
export function size(bytes, per = '') {
  const u = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let i = 0, v = bytes || 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? Math.round(v) : v.toFixed(1)) + ' ' + u[i] + per;
}
