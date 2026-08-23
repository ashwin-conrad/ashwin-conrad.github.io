/* Local structured editor: no framework, no cloud service, no raw JSON fields. */
const state = { documents: null, revisions: null, images: [], selected: "hero", previewTimer: null };
const sections = [
  ["site", "Site setup", "site", [], "Site title, metadata, identity, and navigation shared by every page."],
  ["hero", "Hero", "details", ["portfolio", "hero"], "The first screen visitors see: headline, summary, facts, and photo."],
  ["profile", "Profile", "details", ["portfolio", "profile"], "The engineering profile introduction and three supporting signals."],
  ["case_studies", "Case studies", "details", ["portfolio", "case_studies"], "Featured project stories, figures, captions, tools, and linked résumé IDs."],
  ["experience", "Experience", "details", ["portfolio", "experience"], "Work-history cards on the website. Their stable IDs connect to the résumé."],
  ["skills", "Skills", "details", ["portfolio", "skills"], "Website skill groups and their displayed ordering."],
  ["documentation", "Documentation", "details", ["portfolio", "documentation"], "Image cards, alt text, figure labels, and captions."],
  ["leadership", "Leadership", "details", ["portfolio", "leadership"], "Leadership and engineering-communication cards."],
  ["personal_builds", "Personal builds", "details", ["portfolio", "personal_builds"], "Hands-on project cards, photos, and supporting copy."],
  ["contact", "Contact", "details", ["portfolio", "contact"], "Recruiting call-to-action and links. The email link follows site identity."],
];
const resumeSections = [
  ["resume_intro", "Résumé intro", "resume", ["name"], "Resume-only summary, contact fields, and general skills. Wording here is independent from the website."],
  ["resume_pages", "Résumé sections", "resume", ["pages"], "Résumé page blocks and order. Stable IDs identify roles and projects used by the Word layout."],
  ["resume_sync", "Shared-field rules", "resume", ["_meta", "shared_fields"], "Only these factual paths can sync from site.json. Local résumé edits otherwise win."],
];
const $ = (selector) => document.querySelector(selector);
const clone = (value) => JSON.parse(JSON.stringify(value));
const label = (key) => key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const pathGet = (root, path) => path.reduce((value, key) => value?.[key], root);
const pathSet = (root, path, value) => { let at = root; path.slice(0, -1).forEach((key) => { at = at[key]; }); at[path.at(-1)] = value; };

function setStatus(message, type = "") { const target = $("#status"); target.textContent = message; target.className = type ? `status-${type}` : ""; }
function selected() { return [...sections, ...resumeSections].find(([id]) => id === state.selected); }
function sectionButton(section) { const [id, title] = section; const button = document.createElement("button"); button.textContent = title; button.className = id === state.selected ? "active" : ""; button.onclick = () => { state.selected = id; render(); }; return button; }
function renderNav() { $("#sections").replaceChildren(...sections.map(sectionButton)); $("#resume-sections").replaceChildren(...resumeSections.map(sectionButton)); }
function render() {
  if (!state.documents) return;
  renderNav(); const [, title, documentName, path, help] = selected(); const node = pathGet(state.documents[documentName], path);
  $("#source-label").textContent = `${documentName === "details" ? "details/portfolio · website section" : documentName === "site" ? "site.json · shared site setup" : "resume.json · independent résumé"}`;
  $("#section-title").textContent = title; $("#section-help").textContent = help;
  const form = $("#form");
  form.replaceChildren(state.selected === "resume_intro" ? renderResumeIntro() : renderValue(documentName, path, node, title, true));
  schedulePreview();
}
function renderResumeIntro() {
  const resume = state.documents.resume; const group = document.createElement("section"); group.className = "form";
  ["name", "headline", "contact", "general_skills"].forEach((key) => group.append(renderField("resume", [key], key, resume[key])));
  return group;
}
function renderValue(documentName, path, value, title = "", root = false) {
  if (Array.isArray(value)) return renderArray(documentName, path, value, title);
  if (value && typeof value === "object") {
    const details = document.createElement("details"); details.className = `group ${root ? "root-group" : ""}`; details.open = true;
    const summary = document.createElement("summary"); summary.textContent = title || "Details"; const body = document.createElement("div"); body.className = "group-body";
    Object.entries(value).forEach(([key, child]) => body.append(renderField(documentName, [...path, key], key, child)));
    details.append(summary, body); return details;
  }
  return renderInput(documentName, path, title || "Value", value);
}
function renderField(documentName, path, key, value) {
  if (Array.isArray(value) || (value && typeof value === "object")) return renderValue(documentName, path, value, label(key));
  return renderInput(documentName, path, label(key), value, key);
}
function renderInput(documentName, path, fieldLabel, value, key = "") {
  const wrapper = document.createElement("div"); wrapper.className = "field"; const fieldLabelEl = document.createElement("label"); fieldLabelEl.textContent = fieldLabel; wrapper.append(fieldLabelEl);
  const fixedId = ["id", "resume_id", "resume_ids"].includes(key); const long = String(value ?? "").length > 88 || /description|headline|caption|contribution|objective|context|process|result|text|lead|body|summary/i.test(key);
  const input = long ? document.createElement("textarea") : document.createElement("input"); input.value = value ?? ""; input.readOnly = fixedId; input.dataset.document = documentName; input.dataset.path = JSON.stringify(path); input.oninput = () => { pathSet(state.documents[documentName], path, input.value); schedulePreview(); };
  if (key === "src") {
    input.setAttribute("list", "asset-list"); const image = document.createElement("img"); image.src = value || ""; image.alt = "Selected image preview"; image.onerror = () => { image.removeAttribute("src"); }; const imageBox = document.createElement("div"); imageBox.className = "image-field"; imageBox.append(input, image); wrapper.append(imageBox);
    const upload = document.createElement("input"); upload.type = "file"; upload.accept = "image/*"; upload.onchange = () => importImage(upload.files?.[0], documentName, path, input, image); const uploadRow = document.createElement("div"); uploadRow.className = "upload-row"; uploadRow.append(upload, Object.assign(document.createElement("span"), { textContent: "or select an existing asset above" })); wrapper.append(uploadRow);
  } else { wrapper.append(input); }
  if (fixedId) { const note = document.createElement("small"); note.textContent = "Stable relationship ID — locked in this editor."; wrapper.append(note); }
  return wrapper;
}
function renderArray(documentName, path, values, title) {
  const wrapper = document.createElement("section"); wrapper.className = "array"; const header = document.createElement("div"); header.className = "array-title"; header.append(Object.assign(document.createElement("strong"), { textContent: title || "Items" })); const list = document.createElement("div"); list.className = "array-list";
  values.forEach((value, index) => list.append(renderArrayItem(documentName, path, values, value, index)));
  const add = document.createElement("button"); add.className = "add"; add.textContent = "+ Add item"; add.onclick = () => { values.push(blankItem(values[0], values.length)); render(); };
  wrapper.append(header, list, add); return wrapper;
}
function renderArrayItem(documentName, path, values, value, index) {
  const item = document.createElement("div"); item.className = "array-item"; const toolbar = document.createElement("div"); toolbar.className = "array-toolbar";
  const move = (direction) => { const next = index + direction; if (next < 0 || next >= values.length) return; [values[index], values[next]] = [values[next], values[index]]; render(); };
  [["↑", -1], ["↓", 1]].forEach(([text, direction]) => { const button = document.createElement("button"); button.textContent = text; button.onclick = () => move(direction); toolbar.append(button); });
  const locked = value && typeof value === "object" && value.id; if (!locked) { const remove = document.createElement("button"); remove.textContent = "Remove"; remove.onclick = () => { values.splice(index, 1); render(); }; toolbar.append(remove); }
  item.append(toolbar);
  if (value && typeof value === "object" && !Array.isArray(value)) { if (value.id) item.append(Object.assign(document.createElement("span"), { className: "id-chip", textContent: `ID: ${value.id}` })); item.append(renderValue(documentName, [...path, index], value, itemTitle(value))); }
  else { const row = document.createElement("div"); row.className = "array-primitive"; row.append(Object.assign(document.createElement("span"), { className: "array-index", textContent: String(index + 1).padStart(2, "0") })); const input = document.createElement("input"); input.value = value ?? ""; input.oninput = () => { values[index] = input.value; schedulePreview(); }; row.append(input); item.append(row); }
  return item;
}
function itemTitle(value) { return value.title || value.role || value.heading || value.label || value.text?.slice(0, 55) || "Item"; }
function blankItem(example, index) { if (typeof example === "string" || example == null) return ""; if (Array.isArray(example)) return []; const blank = {}; Object.entries(example).forEach(([key, value]) => { if (key === "id") blank[key] = `new-item-${index + 1}`; else if (key === "resume_id") blank[key] = ""; else if (Array.isArray(value)) blank[key] = []; else if (value && typeof value === "object") blank[key] = blankItem(value, index); else if (typeof value === "boolean") blank[key] = false; else blank[key] = ""; }); return blank; }
async function request(url, body) { const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); const data = await response.json(); if (!response.ok) { const detail = data.errors ? `\n${data.errors.map((error) => `• ${error}`).join("\n")}` : ""; throw new Error((data.error || "Request failed") + detail); } return data; }
async function load() { const response = await fetch("/api/content", { cache: "no-store" }); const data = await response.json(); state.documents = data.documents; state.revisions = data.revisions; state.images = data.images; renderAssetList(); render(); setStatus("Loaded current local content.", "ok"); }
function renderAssetList() { let list = $("#asset-list"); if (!list) { list = document.createElement("datalist"); list.id = "asset-list"; document.body.append(list); } list.replaceChildren(...state.images.map((src) => Object.assign(document.createElement("option"), { value: src }))); }
async function save() { const data = await request("/api/content", { documents: state.documents, revisions: state.revisions }); state.revisions = data.revisions; setStatus("Saved safely to site.json, details.json, and resume.json.", "ok"); }
async function preview() { if (!state.documents) return; try { const data = await request("/api/preview", { documents: state.documents }); $("#preview-frame").srcdoc = data.html; } catch (error) { setStatus(error.message, "error"); } }
function schedulePreview() { clearTimeout(state.previewTimer); state.previewTimer = setTimeout(preview, 450); }
async function importImage(file, documentName, path, input, image) { if (!file) return; const encoded = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",", 2)[1]); reader.onerror = reject; reader.readAsDataURL(file); }); try { const data = await request("/api/images", { filename: file.name, content_base64: encoded }); state.images = data.images; renderAssetList(); pathSet(state.documents[documentName], path, data.src); input.value = data.src; image.src = data.src; setStatus(`Imported ${file.name} into assets/photos.`, "ok"); } catch (error) { setStatus(error.message, "error"); } }
async function sync(force = false) { try { await save(); const data = await request("/api/sync-shared", { revisions: state.revisions, force }); state.documents.resume = data.resume; state.revisions = data.revisions; render(); setStatus(data.report.join(" · "), "ok"); } catch (error) { setStatus(error.message, "error"); } }
async function build() { try { await save(); const data = await request("/api/build", { revisions: state.revisions }); const output = $("#build-output"); output.hidden = false; output.textContent = data.output || "Build completed."; setStatus("Build completed.", "ok"); } catch (error) { setStatus(error.message, "error"); } }
$("#refresh").onclick = () => load().catch((error) => setStatus(error.message, "error")); $("#save").onclick = () => save().catch((error) => setStatus(error.message, "error")); $("#preview").onclick = () => preview(); $("#sync").onclick = () => sync(false); $("#force-sync").onclick = () => { if (confirm("Overwrite résumé values that have been edited independently?")) sync(true); }; $("#build").onclick = () => build();
load().catch((error) => setStatus(error.message, "error"));
