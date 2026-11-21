// Общая часть виджетов. Раз в секунду читает:
//   theme.json   - цвета темы (пишет ryoku.py)
//   widgets.json - настройки виджетов (пишет панель «Виджеты»)
// Имя виджета берётся из <body data-widget="clock" data-w="1100">.
const me = document.body.dataset.widget;
let lastTheme = '', lastCfg = '';
export let config = {};
export let tools = null;          // чем запускать скрипты: { program, drag, tasks, panel, audio }
let locked = true;                // true = обычный режим: виджеты не выделяются и не двигаются

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
// Всё это работает только в режиме редактирования: он включён, пока открыта панель «Виджеты».
// Войти в него можно правым кликом по любому виджету.
document.addEventListener('contextmenu', async e => {
  e.preventDefault();
  if (!tools || !tools.panel || !locked) return;
  try { await exec([tools.panel, me]); } catch (err) { console.error('panel', err); }
});
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

// Общий опрос файлов: читает только один виджет (кто взял замок), остальные получают текст
// через BroadcastChannel. Раньше каждое из 8 окон само читало файлы каждую секунду.
// Замок и канал общие только для окон одного источника; если их нет - каждый читает сам, как раньше.
const shareCh = ('BroadcastChannel' in window) ? new BroadcastChannel('ryoku-files') : null;
const shareCache = {};
let leader = !(shareCh && navigator.locks);
if (!leader) {
  shareCh.onmessage = e => { if (e.data && e.data.f) shareCache[e.data.f] = e.data.t; };
  navigator.locks.request('ryoku-poll', () => { leader = true; return new Promise(() => {}); }).catch(() => { leader = true; });
}
async function shared(file) {
  if (!leader && file in shareCache) return shareCache[file];
  const t = await read(file);
  if (leader && shareCh) shareCh.postMessage({ f: file, t });
  shareCache[file] = t;
  return t;
}

let pollN = 0;
async function poll() {
  try {
    // тема меняется редко: читаем её раз в три секунды, настройки виджетов - каждую секунду
    const txt = pollN++ % 3 ? '' : await shared('theme.json');
    if (txt && txt !== lastTheme) {
      lastTheme = txt;
      const t = JSON.parse(txt);
      theme = t;
      paint();
      if (t.wall) document.documentElement.style.setProperty('--wall-img', "url('./" + t.wall + '?v=' + (t.wallv || 0) + "')");
      if (t.screen) screenSize = t.screen;
      wallImg = null;
      contrastSoon();
      document.dispatchEvent(new CustomEvent('theme', { detail: t }));
    }
  } catch (e) {}
  try {
    const txt = await shared('widgets.json');
    if (txt && txt !== lastCfg) {
      lastCfg = txt;
      const all = JSON.parse(txt);
      config = all[me] || {};
      tools = all._tools || null;
      locked = !(all.all && all.all.edit);
      const g = all.all || {};
      document.documentElement.style.setProperty('--radius', (g.radius ?? 26) + 'px');
      document.documentElement.classList.toggle('noanim', g.anim === false);
      document.documentElement.classList.toggle('nonoise', g.noise === false);
      adapt = g.adapt !== false;
      contrastSoon();
      document.body.style.cursor = locked ? 'default' : 'grab';
      document.documentElement.classList.toggle('editing', !locked);
      document.documentElement.style.setProperty('--opacity', (config.opacity ?? 100) / 100);
      document.dispatchEvent(new CustomEvent('config', { detail: config }));
    }
  } catch (e) {}
}
poll();
setInterval(poll, 1000);

// Цвета темы. На светлом месте обоев (см. contrast ниже) текст виджета без карточки становится тёмным.
let theme = null, light = false, adapt = true;
function darken(hex, k) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return 'rgb(' + [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * k)).join(',') + ')';
}
function paint() {
  if (!theme) return;
  const s = document.documentElement.style;
  for (const k of ['fg', 'muted', 'accent', 'accent2', 'accent3', 'glow', 'pill', 'line', 'glass', 'edge']) {
    if (theme[k]) s.setProperty('--' + k, theme[k]);
  }
  if (light) {
    s.setProperty('--fg', '#17171e');
    s.setProperty('--muted', '#50505c');
    for (const k of ['accent', 'accent2', 'accent3', 'glow']) s.setProperty('--' + k, darken(theme[k], k === 'glow' ? 0.34 : 0.48));
    s.setProperty('--line', 'rgba(0, 0, 0, 0.16)');
  }
  document.documentElement.classList.toggle('on-light', light);
  // плавная смена цветов включается только после первой отрисовки: при запуске виджет сразу в своих цветах
  if (!document.documentElement.classList.contains('tween'))
    requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.add('tween')));
}

// Адаптивный контраст: берём размытую копию обоев, смотрим среднюю яркость под окном виджета.
// Если там светло, а карточки у виджета нет, белый текст не читается - переключаемся на тёмный.
let wallImg = null, contrastTimer = 0;
function contrastSoon() { clearTimeout(contrastTimer); contrastTimer = setTimeout(contrast, 350); }
async function contrast() {
  let want = false;
  try {
    if (adapt && theme && theme.wall && !document.querySelector('.box.card-bg, .wrap.card-bg, .card.card-bg, .ph.card-bg')) {
      if (!wallImg) {
        wallImg = new Image();
        wallImg.src = './' + theme.wall + '?v=' + (theme.wallv || 0);
        await wallImg.decode();
      }
      const c = document.createElement('canvas'), W = 16, H = 16;
      c.width = W; c.height = H;
      const kx = wallImg.naturalWidth / screen.width, ky = wallImg.naturalHeight / screen.height;
      const g = c.getContext('2d', { willReadFrequently: true });
      g.drawImage(wallImg, window.screenX * kx, window.screenY * ky, window.innerWidth * kx, window.innerHeight * ky, 0, 0, W, H);
      const d = g.getImageData(0, 0, W, H).data;
      let sum = 0;
      for (let i = 0; i < d.length; i += 4) sum += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      const lum = sum / (W * H) / 255;
      document.documentElement.dataset.lum = lum.toFixed(2);          // для проверки: яркость обоев под виджетом
      want = light ? lum > 0.52 : lum > 0.60;         // с запасом, чтобы цвет не мигал на границе
    }
  } catch (e) { want = false; document.documentElement.dataset.lum = 'err ' + e; }
  if (want !== light) { light = want; paint(); }
}
document.addEventListener('config', contrastSoon);

// Появление виджета: короткое проявление со сдвигом. Обычное состояние страницы - видимое,
// скрывает её только класс enter, который снимается по таймеру. Если что-то пойдёт не так, виджет останется виден.
document.documentElement.classList.add('enter');
setTimeout(() => document.documentElement.classList.remove('enter'), 60 + Math.random() * 220);

// Стекло: размытые обои внутри карточек должны совпадать с настоящими обоями за окном.
// Для этого фон каждой карточки сдвигается на положение окна на экране и самой карточки в окне.
let screenSize = [screen.width, screen.height], glassKey = '';
function glassTick() {
  const z = parseFloat(document.body.style.zoom) || 1;
  const key = [window.screenX, window.screenY, z, screenSize[0], document.querySelectorAll('.card-bg').length].join();
  if (key === glassKey) return;
  glassKey = key;
  contrastSoon();
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
