"use strict";

const MONTH_NAMES = ["January","February","March","April","May","June",
  "July","August","September","October","November","December"];

let EVENTS = {};        // "YYYY-MM-DD" -> [event, ...]
let viewYear, viewMonth; // month is 0-indexed

const grid = document.getElementById("grid");
const monthLabel = document.getElementById("monthLabel");
const modal = document.getElementById("modal");
const modalDate = document.getElementById("modalDate");
const modalBody = document.getElementById("modalBody");

function ymd(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function todayStr() {
  const t = new Date();
  return ymd(t.getFullYear(), t.getMonth(), t.getDate());
}

function render() {
  monthLabel.textContent = `${MONTH_NAMES[viewMonth]} ${viewYear}`;
  grid.innerHTML = "";

  const firstDow = new Date(viewYear, viewMonth, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const today = todayStr();

  // total cells: pad to full weeks
  const totalCells = Math.ceil((firstDow + daysInMonth) / 7) * 7;

  for (let i = 0; i < totalCells; i++) {
    const dayNum = i - firstDow + 1;
    const cell = document.createElement("div");
    cell.className = "cell";

    if (dayNum < 1 || dayNum > daysInMonth) {
      cell.classList.add("outside");
      grid.appendChild(cell);
      continue;
    }

    const dow = (firstDow + dayNum - 1) % 7;
    if (dow === 0 || dow === 6) cell.classList.add("weekend");

    const dateKey = ymd(viewYear, viewMonth, dayNum);
    if (dateKey === today) cell.classList.add("today");

    const num = document.createElement("div");
    num.className = "day-num";
    num.textContent = dayNum;
    cell.appendChild(num);

    const dayEvents = EVENTS[dateKey] || [];
    if (dayEvents.some((e) => e.type === "holiday")) cell.classList.add("closed");
    if (dayEvents.length) {
      cell.classList.add("has-events");
      const pills = document.createElement("div");
      pills.className = "pills";
      for (const ev of dayEvents) {
        const pill = document.createElement("div");
        pill.className = "pill";
        if (ev.type === "holiday") pill.classList.add("holiday");
        else if (ev.type === "early_close") pill.classList.add("early");
        pill.textContent = ev.name;
        pills.appendChild(pill);
      }
      cell.appendChild(pills);
      cell.addEventListener("click", () => openModal(dateKey, dayEvents));
    }

    grid.appendChild(cell);
  }
}

function openModal(dateKey, dayEvents) {
  modalDate.textContent = dateKey;
  modalBody.innerHTML = "";
  for (const ev of dayEvents) {
    const item = document.createElement("div");
    item.className = "event-item";
    const name = document.createElement("div");
    name.className = "event-name";
    name.textContent = ev.title || ev.name;
    item.appendChild(name);
    if (ev.desc) {
      const desc = document.createElement("div");
      desc.className = "event-desc";
      desc.textContent = ev.desc;
      item.appendChild(desc);
    }
    modalBody.appendChild(item);
  }
  modal.hidden = false;
}

function closeModal() { modal.hidden = true; }

function shiftMonth(delta) {
  viewMonth += delta;
  if (viewMonth < 0) { viewMonth = 11; viewYear--; }
  else if (viewMonth > 11) { viewMonth = 0; viewYear++; }
  render();
}

document.getElementById("prevBtn").addEventListener("click", () => shiftMonth(-1));
document.getElementById("nextBtn").addEventListener("click", () => shiftMonth(1));
document.getElementById("modalClose").addEventListener("click", closeModal);
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

async function init() {
  const now = new Date();
  viewYear = now.getFullYear();
  viewMonth = now.getMonth();
  try {
    const res = await fetch("data.json", { cache: "no-store" });
    const data = await res.json();
    for (const ev of data.events || []) {
      (EVENTS[ev.date] = EVENTS[ev.date] || []).push(ev);
    }
    const maxYear = Math.max(...(data.years || [now.getFullYear()]));
    // 每年 12/10 起提醒补下一年数据（下一年官方日程 9 月下旬已公布）
    if (now >= new Date(maxYear, 11, 10)) {
      document.getElementById("staleYear").textContent = maxYear + 1;
      document.getElementById("staleBanner").hidden = false;
    }
  } catch (err) {
    console.error("加载 data.json 失败：", err);
  }
  render();
}

init();
