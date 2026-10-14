"use strict";
const $ = (id) => document.getElementById(id);
let example, current = null, previous = null, busy = false, extractionPending = false;
let revision = 0;
const colors = ["#21785a", "#3687a0", "#a36193", "#bf8730", "#5d6ba5", "#839c4c"];
const number = (v) => new Intl.NumberFormat("en-GB", {maximumFractionDigits: 6}).format(v);
const money = (v) => new Intl.NumberFormat("en-GB", {style: "currency", currency: "EUR"}).format(v);
const mode = () => document.querySelector('input[name="mode"]:checked').value;

function message(text = "") { $("message").textContent = text; $("message").hidden = !text; }
function invalidate() {
  revision++;
  if (current) previous = current;
  current = null;
  $("result").hidden = true; $("empty").hidden = false;
  $("empty-text").textContent = "Data changed. A new optimization is required.";
  $("status").textContent = "Awaiting optimization";
  $("download").disabled = true; $("confirm").checked = false;
}
function setBusy(value, operation = "") {
  busy = value;
  document.querySelectorAll("button, input, textarea").forEach(el => { el.disabled = value; });
  $("download").disabled = value || !current;
  $("extract").textContent = value && operation === "extract" ? "Extracting…" : "Extract data";
  $("solve").textContent = value && operation === "solve" ? "Optimizing…" : "Optimize load";
  document.querySelector("main").setAttribute("aria-busy", String(value));
}
async function request(path, payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 75000);
  try {
    const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", "X-ApertusOpt": "1"}, body: JSON.stringify(payload), signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The request failed.");
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The request timed out. Please try again shortly.");
    if (error instanceof TypeError) throw new Error("Cannot reach the local server. Check that web_app.py is running.");
    throw error;
  } finally { clearTimeout(timer); }
}
function addRow(item = {name: "", weight: "", volume: "", value: ""}) {
  if ($("items").children.length >= 500) return message("The web demo supports at most 500 pallets.");
  const row = document.createElement("tr");
  for (const key of ["name", "weight", "volume", "value"]) {
    const td = document.createElement("td"), input = document.createElement("input");
    input.type = key === "name" ? "text" : "number"; input.required = true;
    input.dataset.field = key; input.value = item[key];
    if (key !== "name") { input.step = "any"; if (key !== "value") input.min = "0.0000000001"; }
    if (key === "name") input.maxLength = 120;
    td.append(input); row.append(td);
  }
  const td = document.createElement("td"), remove = document.createElement("button");
  remove.type = "button"; remove.textContent = "×";
  remove.addEventListener("click", () => { row.remove(); invalidate(); labelRows(); });
  td.append(remove); row.append(td); $("items").append(row); labelRows();
}
function labelRows() {
  Array.from($("items").children).forEach((row, index) => {
    row.querySelectorAll("input").forEach(input => input.setAttribute("aria-label", `Pallet ${index + 1} ${input.dataset.field}`));
    const button = row.querySelector("button");
    button.title = `Remove pallet ${index + 1}`; button.setAttribute("aria-label", button.title);
  });
  $("count").textContent = $("items").children.length;
}
function fillData(problem, source) {
  invalidate(); $("capacity").value = problem.capacity; $("volume-capacity").value = problem.volume_capacity;
  $("items").replaceChildren(); problem.items.forEach(addRow); $("source").textContent = source;
}
function readData() {
  const items = Array.from($("items").children).map(row => {
    const item = {};
    row.querySelectorAll("input").forEach(input => { item[input.dataset.field] = input.dataset.field === "name" ? input.value.trim() : Number(input.value); });
    return item;
  });
  if (!items.length) throw new Error("Add at least one pallet.");
  return {problem_type: "knapsack", sense: "maximize", capacity: Number($("capacity").value), volume_capacity: Number($("volume-capacity").value), items};
}
function renderResult(report) {
  current = report;
  const s = report.solution, p = report.problem;
  $("empty").hidden = true; $("result").hidden = false;
  $("status").textContent = s.status === "OPTIMAL" ? "Optimal · verified" : "Feasible · not proven optimal";
  $("margin").textContent = money(s.total_value);
  $("weight").textContent = `${number(s.total_weight)} / ${number(p.capacity)} kg`;
  $("volume").textContent = `${number(s.total_volume)} / ${number(p.volume_capacity)} m³`;
  $("weight-left").textContent = `${number(report.remaining_weight)} kg remaining`;
  $("volume-left").textContent = `${number(report.remaining_volume)} m³ remaining`;
  $("selected-count").textContent = `${s.selected_items.length} / ${p.items.length}`;
  $("solve-time").textContent = `Solver: ${number(report.solve_seconds)} s`;
  $("comparison").textContent = previous ? `${money(s.total_value - previous.solution.total_value)} vs previous run (${money(previous.solution.total_value)})` : "First scenario";
  $("summary").textContent = report.summary;
  $("selected").textContent = s.selected_items.join(", ") || "None";
  $("excluded").textContent = report.excluded_items.join(", ") || "None";
  $("download").disabled = false;
  drawAllocation();
}
function drawAllocation() {
  if (!current) return;
  const canvas = $("allocation"), width = canvas.clientWidth, height = 150;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr); canvas.height = height * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const chosen = current.problem.items.filter(i => current.solution.selected_items.includes(i.name));
  // Aggregate long inventories so the chart and legend stay readable.
  const groups = chosen.slice(0, 5).map(i => ({...i}));
  if (chosen.length > 5) groups.push({name: `${chosen.length - 5} more pallets`, weight: chosen.slice(5).reduce((s, i) => s + i.weight, 0), volume: chosen.slice(5).reduce((s, i) => s + i.volume, 0)});
  const chartWidth = Math.max(1, width - 2);
  for (const [index, field] of ["weight", "volume"].entries()) {
    const capacity = field === "weight" ? current.problem.capacity : current.problem.volume_capacity;
    const total = field === "weight" ? current.solution.total_weight : current.solution.total_volume;
    const y = 25 + index * 65;
    ctx.font = "12px Segoe UI, sans-serif"; ctx.fillStyle = "#64726b";
    ctx.fillText(field === "weight" ? "Payload" : "Volume", 0, y - 8);
    ctx.textAlign = "right"; ctx.fillText(`${number(total / capacity * 100)}% used`, width - 2, y - 8); ctx.textAlign = "left";
    ctx.fillStyle = "#e1e8e3"; ctx.fillRect(0, y, chartWidth, 24);
    let left = 0;
    groups.forEach((group, n) => { const size = Math.min(chartWidth - left, group[field] / capacity * chartWidth); ctx.fillStyle = colors[n]; ctx.fillRect(left, y, size, 24); left += size; });
  }
  $("legend").replaceChildren();
  [...groups.map((g, i) => ({name: g.name, color: colors[i]})), {name: "Available", color: "#e1e8e3"}].forEach(group => {
    const item = document.createElement("span"), swatch = document.createElement("canvas"), label = document.createElement("span");
    item.className = "legend-item"; swatch.className = "swatch"; swatch.width = swatch.height = 9;
    swatch.getContext("2d").fillStyle = group.color; swatch.getContext("2d").fillRect(0, 0, 9, 9);
    label.textContent = group.name; item.append(swatch, label); $("legend").append(item);
  });
}
$("data-form").addEventListener("input", (event) => { if (event.target.id !== "confirm") { invalidate(); $("source").textContent = "Edited data"; } });
$("description").addEventListener("input", () => { extractionPending = true; invalidate(); $("source").textContent = "Brief changed · extract again"; });
document.querySelectorAll('input[name="mode"]').forEach(el => el.addEventListener("change", () => {
  extractionPending = true; invalidate();
  $("mode-note").textContent = mode() === "demo" ? "Demo uses fixed example data, not your description." : "Your description will be sent to the configured Apertus API.";
  $("source").textContent = "Source changed · extract again";
}));
$("add").addEventListener("click", () => { invalidate(); addRow(); });
$("example").addEventListener("click", () => {
  if (!example) return;
  $("description").value = example.text; extractionPending = false;
  fillData(example.problem, "Example data"); message(); $("extraction-time").textContent = "Example loaded · no API call";
});
$("extract").addEventListener("click", async () => {
  if (busy) return;
  message(); invalidate(); extractionPending = true;
  setBusy(true, "extract");
  try {
    const data = await request("/api/extract", {text: $("description").value, mode: mode()});
    fillData(data.problem, data.mode === "demo" ? "Fixed demo data" : "Apertus extraction"); extractionPending = false;
    $("extraction-time").textContent = `Extraction: ${number(data.extract_seconds)} s`;
  } catch (error) { message(error.message); }
  finally { setBusy(false); }
});
$("data-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return; message();
  if (extractionPending) return message("The brief or extraction source changed. Extract data again, or load the example.");
  let data;
  try { data = readData(); } catch (error) { return message(error.message); }
  if (current) previous = current;
  invalidate(); setBusy(true, "solve"); const requestedRevision = revision;
  try {
    const report = await request("/api/solve", data);
    if (revision === requestedRevision) { renderResult(report); $("confirm").checked = true; }
  } catch (error) { message(error.message); }
  finally { setBusy(false); }
});
$("download").addEventListener("click", () => {
  if (!current) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(current, null, 2)], {type: "application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = "apertusopt-load-plan.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener("resize", drawAllocation);
(async () => {
  setBusy(true);
  try {
    const response = await fetch("/api/example"); if (!response.ok) throw new Error("Could not load the example.");
    example = await response.json(); $("description").value = example.text; fillData(example.problem, "Example data");
    $("empty-text").textContent = "No verified load plan yet.";
  } catch { message("Cannot load the workspace. Check that the local server is running and reload."); }
  finally { setBusy(false); }
})();
