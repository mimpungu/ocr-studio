const BLOCK_COLORS = {
  "Section-Header": "oklch(48% .2 263)",
  Text: "oklch(58% .15 145)",
  "List-Group": "oklch(58% .16 195)",
  Table: "oklch(62% .18 45)",
  Caption: "oklch(55% .16 310)",
  Footnote: "oklch(52% .08 263)",
  "Page-Header": "oklch(65% .04 263)",
  "Page-Footer": "oklch(65% .04 263)",
};

const MODE_HINTS = {
  auto: "Lit la couche texte du PDF si elle est fiable, sinon OCR visuel.",
  ocr: "Ignore la couche texte et lit chaque page visuellement.",
  text: "Force l'utilisation de la couche texte du PDF.",
};

const state = {
  file: null,
  doc: null,
  undoStack: [],
  mode: "auto",
  regionMode: false,
  lastRegionPageIdx: 0,
  lastRegionBbox: null,
};

const els = {
  drop: document.getElementById("drop"),
  fileInput: document.getElementById("fileInput"),
  fname: document.getElementById("fname"),
  modeSeg: document.getElementById("modeSeg"),
  modeHint: document.getElementById("modeHint"),
  postprocessChk: document.getElementById("postprocessChk"),
  enhanceScanChk: document.getElementById("enhanceScanChk"),
  photoModeChk: document.getElementById("photoModeChk"),
  mathChk: document.getElementById("mathChk"),
  furnitureChk: document.getElementById("furnitureChk"),
  dpiSelect: document.getElementById("dpiSelect"),
  regionToolBtn: document.getElementById("regionToolBtn"),
  reprocessBtn: document.getElementById("reprocessBtn"),
  findInput: document.getElementById("findInput"),
  replaceInput: document.getElementById("replaceInput"),
  replaceAllBtn: document.getElementById("replaceAllBtn"),
  undoBtn: document.getElementById("undoBtn"),
  anonymizeBtn: document.getElementById("anonymizeBtn"),
  entitiesBox: document.getElementById("entitiesBox"),
  showLinesChk: document.getElementById("showLinesChk"),
  showBlocksChk: document.getElementById("showBlocksChk"),
  showLabelsChk: document.getElementById("showLabelsChk"),
  showOrderChk: document.getElementById("showOrderChk"),
  stats: document.getElementById("stats"),
  status: document.getElementById("status"),
  exportBtn: document.getElementById("exportBtn"),
  exportMenu: document.getElementById("exportMenu"),
  emptyState: document.getElementById("emptyState"),
  pagesContainer: document.getElementById("pagesContainer"),
  regionModal: document.getElementById("regionModal"),
  closeRegionModal: document.getElementById("closeRegionModal"),
  regionMeta: document.getElementById("regionMeta"),
  regionResultText: document.getElementById("regionResultText"),
  copyRegionBtn: document.getElementById("copyRegionBtn"),
  insertRegionBlockBtn: document.getElementById("insertRegionBlockBtn"),
};

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pushUndo() {
  if (!state.doc) return;
  const snapshot = JSON.stringify(state.doc.pages.map((p) => p.blocks));
  state.undoStack.push(snapshot);
  if (state.undoStack.length > 25) state.undoStack.shift();
  els.undoBtn.disabled = false;
}

function renderEntities() {
  const ents = state.doc?.entities;
  if (!ents) {
    els.entitiesBox.innerHTML = "Aucun champ extrait.";
    return;
  }
  const labels = [
    ["emails", "Emails"],
    ["phones", "Tél"],
    ["dates", "Dates"],
    ["amounts", "Montants"],
    ["ibans", "IBAN"],
  ];
  const rows = [];
  for (const [k, lbl] of labels) {
    if (ents[k] && ents[k].length) {
      rows.push(`<div><b>${lbl}:</b> ${esc(ents[k].slice(0, 4).join(", "))}${ents[k].length > 4 ? "…" : ""}</div>`);
    }
  }
  els.entitiesBox.innerHTML = rows.length
    ? `<div class="ent-list">${rows.join("")}</div>`
    : "Aucun champ clé détecté.";
}

function confClass(c) {
  if (c >= 0.95) return "conf-hi";
  if (c >= 0.8) return "conf-md";
  return "conf-lo";
}

function syncOverlayClasses() {
  document.querySelectorAll(".page-stage").forEach((st) => {
    st.classList.toggle("hide-lines", !els.showLinesChk.checked);
    st.classList.toggle("hide-blocks", !els.showBlocksChk.checked);
    st.classList.toggle("hide-labels", !els.showLabelsChk.checked);
    st.classList.toggle("hide-order", !els.showOrderChk.checked);
    st.classList.toggle("region-mode", state.regionMode);
  });
}

function syncMarkdown(page) {
  const parts = [];
  for (const b of page.blocks) {
    const t = (b.text || "").trim();
    if (!t) continue;
    parts.push(b.label === "Section-Header" ? `## ${t}` : t);
  }
  page.markdown = parts.join("\n\n");
}

function renderMarkdownPreviewHtml(md) {
  const blocks = md.split(/\n{2,}/);
  return blocks
    .map((b) => {
      const t = b.trim();
      if (!t) return "";
      if (t.startsWith("<table")) return t;
      if (t.startsWith("## ")) return `<h2>${esc(t.slice(3))}</h2>`;
      if (t.startsWith("# ")) return `<h1>${esc(t.slice(2))}</h1>`;
      return `<p>${esc(t).replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

function serializeTable(tbl) {
  const rows = [];
  tbl.querySelectorAll("tr").forEach((tr) => {
    const cells = [];
    tr.querySelectorAll("th, td").forEach((cell) => {
      const tag = cell.tagName.toLowerCase();
      cells.push(`<${tag}>${esc(cell.textContent.trim())}</${tag}>`);
    });
    if (cells.length) rows.push(`<tr>${cells.join("")}</tr>`);
  });
  return `<table>\n${rows.join("\n")}\n</table>`;
}

function buildSvgOverlay(svg, page, pIdx, onSelectBlock) {
  svg.setAttribute("viewBox", `0 0 ${page.width} ${page.height}`);
  svg.innerHTML = "";

  const img = document.createElementNS("http://www.w3.org/2000/svg", "image");
  img.setAttribute("href", page.image_data_url);
  img.setAttribute("width", page.width);
  img.setAttribute("height", page.height);
  svg.appendChild(img);

  // Lignes
  page.lines.forEach((ln, lIdx) => {
    const [x0, y0, x1, y1] = ln.box;
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("class", "ln");
    r.setAttribute("data-ln", lIdx);
    r.setAttribute("x", x0);
    r.setAttribute("y", y0);
    r.setAttribute("width", Math.max(1, x1 - x0));
    r.setAttribute("height", Math.max(1, y1 - y0));
    svg.appendChild(r);
  });

  // Blocs + labels
  const centers = [];
  page.blocks.forEach((b, bIdx) => {
    const [x0, y0, x1, y1] = b.bbox;
    if (x1 <= x0 || y1 <= y0) return;
    const color = BLOCK_COLORS[b.label] || "oklch(50% .12 263)";

    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("class", "bk");
    r.setAttribute("data-bk", b.id);
    r.setAttribute("x", x0);
    r.setAttribute("y", y0);
    r.setAttribute("width", x1 - x0);
    r.setAttribute("height", y1 - y0);
    r.setAttribute("stroke", color);
    r.addEventListener("click", (ev) => {
      if (state.regionMode) return;
      ev.stopPropagation();
      onSelectBlock(b.id);
    });
    svg.appendChild(r);

    const lbl = document.createElementNS("http://www.w3.org/2000/svg", "text");
    lbl.setAttribute("class", "bl");
    lbl.setAttribute("x", x0 + 3);
    lbl.setAttribute("y", Math.max(14, y0 - 4));
    lbl.setAttribute("font-size", Math.max(11, Math.round(page.width * 0.011)));
    lbl.setAttribute("fill", color);
    lbl.textContent = b.label;
    svg.appendChild(lbl);

    centers.push([(x0 + x1) / 2, (y0 + y1) / 2, bIdx + 1]);
  });

  // Ordre de lecture
  if (centers.length > 1) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("class", "ord");
    path.setAttribute("d", centers.map((c, i) => `${i === 0 ? "M" : "L"}${c[0]} ${c[1]}`).join(" "));
    svg.appendChild(path);
  }
  const rad = Math.max(10, Math.round(page.width * 0.011));
  centers.forEach(([cx, cy, num]) => {
    const circ = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circ.setAttribute("class", "on-n");
    circ.setAttribute("cx", cx);
    circ.setAttribute("cy", cy);
    circ.setAttribute("r", rad);
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("class", "n");
    txt.setAttribute("x", cx);
    txt.setAttribute("y", cy);
    txt.setAttribute("font-size", Math.round(rad * 1.1));
    txt.textContent = num;
    svg.appendChild(circ);
    svg.appendChild(txt);
  });

  // Lasso Re-OCR zone
  let start = null;
  let tempRect = null;
  const toImg = (ev) => {
    const rect = svg.getBoundingClientRect();
    return [
      ((ev.clientX - rect.left) / rect.width) * page.width,
      ((ev.clientY - rect.top) / rect.height) * page.height,
    ];
  };
  svg.addEventListener("mousedown", (ev) => {
    if (!state.regionMode) return;
    start = toImg(ev);
    tempRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    tempRect.setAttribute("fill", "oklch(38% .24 263 / .2)");
    tempRect.setAttribute("stroke", "oklch(38% .24 263)");
    tempRect.setAttribute("stroke-width", "3");
    tempRect.setAttribute("stroke-dasharray", "6 4");
    svg.appendChild(tempRect);
  });
  svg.addEventListener("mousemove", (ev) => {
    if (!start || !tempRect) return;
    const [x, y] = toImg(ev);
    tempRect.setAttribute("x", Math.min(start[0], x));
    tempRect.setAttribute("y", Math.min(start[1], y));
    tempRect.setAttribute("width", Math.abs(x - start[0]));
    tempRect.setAttribute("height", Math.abs(y - start[1]));
  });
  window.addEventListener("mouseup", async (ev) => {
    if (!start || !tempRect) return;
    const [x, y] = toImg(ev);
    const bbox = [Math.min(start[0], x), Math.min(start[1], y), Math.max(start[0], x), Math.max(start[1], y)];
    start = null;
    tempRect.remove();
    tempRect = null;
    if (bbox[2] - bbox[0] < 10 || bbox[3] - bbox[1] < 10) return;

    state.lastRegionPageIdx = pIdx;
    state.lastRegionBbox = bbox;
    els.status.textContent = "Re-OCR haute résolution en cours...";
    try {
      const res = await fetch("/api/ocr-region", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_data_url: page.image_data_url,
          bbox,
          math: els.mathChk.checked,
          upscale: 2.0,
          enhance: true,
          postprocess: els.postprocessChk.checked,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur Re-OCR");
      els.regionMeta.textContent = `Confiance : ${Math.round(data.mean_conf * 100)}% · ${data.lines.length} ligne(s)`;
      els.regionResultText.value = data.text;
      els.regionModal.classList.remove("hidden");
      els.status.textContent = "Re-OCR ciblé terminé.";
    } catch (e) {
      els.status.textContent = `Erreur : ${e.message}`;
    }
  });
}

function renderPageCard(page, pIdx) {
  const card = document.createElement("article");
  card.className = "card";

  const t = page.timings || {};
  const tot = Math.max(1, t.total_ms || 1);
  const detPct = Math.round(((t.det_ms || 0) / tot) * 100);
  const recPct = Math.round(((t.rec_ms || 0) / tot) * 100);

  card.innerHTML = `
    <div class="ch">
      <h3>Page ${page.page_num}</h3>
      <span class="chip ${page.source}">${page.source}</span>
      <span class="meta">${page.lines.length} lignes · ${page.blocks.length} blocs · conf ${Math.round(page.mean_conf * 100)}% · ${Math.round(tot)} ms</span>
      <div class="sp"></div>
      <div class="tbar" title="Détection / Reconnaissance">
        <i style="width:${detPct}%;background:oklch(55% .15 263)"></i>
        <i style="width:${recPct}%;background:oklch(58% .15 145)"></i>
      </div>
    </div>
    <div class="body">
      <div class="pageview">
        <div class="page-stage">
          <svg class="pg"></svg>
        </div>
      </div>
      <div class="right">
        <div class="tabs">
          <button class="tab on" data-t="edit">Éditeur direct</button>
          <button class="tab" data-t="preview">Aperçu</button>
          <button class="tab" data-t="md">Markdown</button>
          <button class="tab" data-t="lines">Lignes</button>
          <button class="tab" data-t="json">JSON</button>
          <div class="sp"></div>
          <button class="btn-outline small add-blk-btn">+ Bloc</button>
        </div>
        <div class="pane" data-p="edit"></div>
        <div class="pane preview hidden" data-p="preview"></div>
        <div class="pane src hidden" data-p="md"><textarea></textarea></div>
        <div class="pane hidden" data-p="lines"></div>
        <div class="pane src hidden" data-p="json"><pre class="mono" style="margin:0;font-size:12px"></pre></div>
      </div>
    </div>
  `;

  const svg = card.querySelector("svg.pg");
  const editPane = card.querySelector('[data-p="edit"]');
  const previewPane = card.querySelector('[data-p="preview"]');
  const mdTa = card.querySelector('[data-p="md"] textarea');
  const linesPane = card.querySelector('[data-p="lines"]');
  const jsonPre = card.querySelector('[data-p="json"] pre');

  const refreshViews = () => {
    syncMarkdown(page);
    mdTa.value = page.markdown;
    previewPane.innerHTML = renderMarkdownPreviewHtml(page.markdown);
    const clean = { ...page };
    delete clean.image_data_url;
    jsonPre.textContent = JSON.stringify(clean, null, 2);
  };

  const selectBlock = (blkId) => {
    svg.querySelectorAll("rect.bk").forEach((r) => r.classList.toggle("on", r.dataset.bk === blkId));
    editPane.querySelectorAll(".blk-card").forEach((c) => {
      const m = c.dataset.bk === blkId;
      c.classList.toggle("on", m);
      if (m) c.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  };

  const renderBlocks = () => {
    editPane.innerHTML = "";
    const list = document.createElement("div");
    list.className = "blocks-list";
    const labels = ["Section-Header", "Text", "List-Group", "Table", "Caption", "Footnote", "Page-Header", "Page-Footer"];

    page.blocks.forEach((blk, bIdx) => {
      const bc = document.createElement("div");
      bc.className = "blk-card";
      bc.dataset.bk = blk.id;
      bc.addEventListener("click", () => selectBlock(blk.id));

      const head = document.createElement("div");
      head.className = "blk-head";
      const left = document.createElement("div");
      left.style.display = "flex";
      left.style.gap = "8px";
      left.style.alignItems = "center";

      const sel = document.createElement("select");
      labels.forEach((l) => {
        const o = document.createElement("option");
        o.value = l;
        o.textContent = l;
        if (l === blk.label) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener("change", () => {
        blk.label = sel.value;
        refreshViews();
        renderBlocks();
      });

      const pill = document.createElement("span");
      pill.className = `conf-tag ${confClass(blk.conf)}`;
      pill.textContent = `${Math.round(blk.conf * 100)}%`;

      left.appendChild(sel);
      left.appendChild(pill);

      const actionsWrap = document.createElement("div");
      actionsWrap.className = "blk-actions";

      const upBtn = document.createElement("button");
      upBtn.className = "btn-outline small";
      upBtn.textContent = "↑";
      upBtn.disabled = bIdx === 0;
      upBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        pushUndo();
        [page.blocks[bIdx - 1], page.blocks[bIdx]] = [page.blocks[bIdx], page.blocks[bIdx - 1]];
        refreshViews();
        renderBlocks();
      });

      const downBtn = document.createElement("button");
      downBtn.className = "btn-outline small";
      downBtn.textContent = "↓";
      downBtn.disabled = bIdx === page.blocks.length - 1;
      downBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        pushUndo();
        [page.blocks[bIdx + 1], page.blocks[bIdx]] = [page.blocks[bIdx], page.blocks[bIdx + 1]];
        refreshViews();
        renderBlocks();
      });

      const delBtn = document.createElement("button");
      delBtn.className = "btn-outline small";
      delBtn.textContent = "Suppr.";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        pushUndo();
        page.blocks.splice(bIdx, 1);
        refreshViews();
        renderBlocks();
        buildSvgOverlay(svg, page, pIdx, selectBlock);
      });

      actionsWrap.appendChild(upBtn);
      actionsWrap.appendChild(downBtn);
      actionsWrap.appendChild(delBtn);

      head.appendChild(left);
      head.appendChild(actionsWrap);
      bc.appendChild(head);

      if (blk.label === "Table" && blk.text.includes("<table")) {
        const wrap = document.createElement("div");
        wrap.className = "tbl-edit-wrap";
        const tmp = document.createElement("div");
        tmp.innerHTML = blk.text;
        const tbl = tmp.querySelector("table");
        if (tbl) {
          tbl.className = "tbl-edit";
          tbl.querySelectorAll("th, td").forEach((cell) => {
            cell.setAttribute("contenteditable", "true");
            cell.addEventListener("input", () => {
              blk.text = serializeTable(tbl);
              refreshViews();
            });
          });
          wrap.appendChild(tbl);
          const bar = document.createElement("div");
          bar.className = "tbl-bar";
          const addRow = document.createElement("button");
          addRow.className = "btn-outline small";
          addRow.textContent = "+ Ligne";
          addRow.addEventListener("click", () => {
            const first = tbl.querySelector("tr");
            const ncols = first ? first.children.length : 2;
            const tr = document.createElement("tr");
            for (let i = 0; i < ncols; i++) {
              const td = document.createElement("td");
              td.setAttribute("contenteditable", "true");
              td.addEventListener("input", () => {
                blk.text = serializeTable(tbl);
                refreshViews();
              });
              tr.appendChild(td);
            }
            tbl.appendChild(tr);
            blk.text = serializeTable(tbl);
            refreshViews();
          });
          const addCol = document.createElement("button");
          addCol.className = "btn-outline small";
          addCol.textContent = "+ Colonne";
          addCol.addEventListener("click", () => {
            pushUndo();
            tbl.querySelectorAll("tr").forEach((tr, rIdx) => {
              const cell = document.createElement(rIdx === 0 && tr.querySelector("th") ? "th" : "td");
              cell.setAttribute("contenteditable", "true");
              cell.addEventListener("input", () => {
                blk.text = serializeTable(tbl);
                refreshViews();
              });
              tr.appendChild(cell);
            });
            blk.text = serializeTable(tbl);
            refreshViews();
          });
          bar.appendChild(addRow);
          bar.appendChild(addCol);
          wrap.appendChild(bar);
        }
        bc.appendChild(wrap);
      } else {
        const ta = document.createElement("textarea");
        ta.className = "blk-ta" + (blk.label === "Section-Header" ? " hdr" : "");
        ta.value = blk.text;
        ta.rows = Math.min(9, Math.max(2, blk.text.split("\n").length + 1));
        ta.addEventListener("input", () => {
          blk.text = ta.value;
          refreshViews();
        });
        bc.appendChild(ta);
      }
      list.appendChild(bc);
    });
    editPane.appendChild(list);
  };

  // Lignes tab
  page.lines.forEach((ln, i) => {
    const row = document.createElement("div");
    row.className = "ln-row";
    row.innerHTML = `<span class="k">${i + 1}</span><span class="t">${esc(ln.text)}</span><span class="c ${ln.conf < 0.85 ? "low" : ""}">${Math.round(ln.conf * 100)}%</span>`;
    row.addEventListener("mouseenter", () => {
      svg.querySelectorAll("rect.ln").forEach((r, idx) => r.classList.toggle("on", idx === i));
    });
    linesPane.appendChild(row);
  });

  // Onglets
  card.querySelectorAll(".tabs .tab").forEach((tb) => {
    tb.addEventListener("click", () => {
      card.querySelectorAll(".tabs .tab").forEach((x) => x.classList.remove("on"));
      card.querySelectorAll(".right .pane").forEach((p) => p.classList.add("hidden"));
      tb.classList.add("on");
      card.querySelector(`[data-p="${tb.dataset.t}"]`).classList.remove("hidden");
    });
  });

  card.querySelector(".add-blk-btn").addEventListener("click", () => {
    page.blocks.push({
      id: `p${page.page_num}_custom_${Date.now()}`,
      label: "Text",
      bbox: [0, 0, 0, 0],
      text: "",
      conf: 1.0,
    });
    renderBlocks();
    refreshViews();
  });

  mdTa.addEventListener("input", () => {
    page.markdown = mdTa.value;
    previewPane.innerHTML = renderMarkdownPreviewHtml(page.markdown);
  });

  buildSvgOverlay(svg, page, pIdx, selectBlock);
  renderBlocks();
  refreshViews();
  return card;
}

async function runOcr(file) {
  state.file = file;
  els.fname.textContent = file.name;
  els.status.textContent = "Analyse OCR en cours...";

  const form = new FormData();
  form.append("file", file);
  form.append("mode", state.mode);
  form.append("dpi", els.dpiSelect.value);
  form.append("postprocess", els.postprocessChk.checked ? "true" : "false");
  form.append("enhance_scan", els.enhanceScanChk.checked ? "true" : "false");
  form.append("photo_mode", els.photoModeChk.checked ? "true" : "false");
  form.append("math", els.mathChk.checked ? "true" : "false");
  form.append("furniture", els.furnitureChk.checked ? "true" : "false");

  try {
    const res = await fetch("/api/ocr", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Erreur OCR");
    }
    state.doc = await res.json();
    state.undoStack = [];
    els.undoBtn.disabled = true;
    els.emptyState.classList.add("hidden");
    els.pagesContainer.classList.remove("hidden");
    els.pagesContainer.innerHTML = "";
    state.doc.pages.forEach((p, idx) => els.pagesContainer.appendChild(renderPageCard(p, idx)));

    els.reprocessBtn.disabled = false;
    els.regionToolBtn.disabled = false;
    els.exportBtn.disabled = false;
    els.replaceAllBtn.disabled = false;
    els.anonymizeBtn.disabled = false;
    renderEntities();

    const totalLines = state.doc.pages.reduce((s, p) => s + p.lines.length, 0);
    const avgConf = Math.round(
      (state.doc.pages.reduce((s, p) => s + p.mean_conf, 0) / state.doc.pages.length) * 100
    );
    els.stats.innerHTML = `<b>${state.doc.page_count}</b> page(s) · <b>${totalLines}</b> lignes<br>Confiance moy. <b>${avgConf}%</b> · <b>${state.doc.total_ms} ms</b>`;
    els.status.textContent = "Prêt — éditez directement les blocs ou tableaux à droite.";
    syncOverlayClasses();
  } catch (e) {
    els.status.textContent = `Erreur : ${e.message}`;
  }
}

// Events
els.drop.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", (e) => {
  if (e.target.files[0]) runOcr(e.target.files[0]);
});
els.drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  els.drop.classList.add("over");
});
els.drop.addEventListener("dragleave", () => els.drop.classList.remove("over"));
els.drop.addEventListener("drop", (e) => {
  e.preventDefault();
  els.drop.classList.remove("over");
  if (e.dataTransfer.files[0]) runOcr(e.dataTransfer.files[0]);
});

els.modeSeg.querySelectorAll("button").forEach((btn) => {
  btn.addEventListener("click", () => {
    els.modeSeg.querySelectorAll("button").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    state.mode = btn.dataset.v;
    els.modeHint.textContent = MODE_HINTS[state.mode];
  });
});

els.reprocessBtn.addEventListener("click", () => {
  if (state.file) runOcr(state.file);
});

[els.showLinesChk, els.showBlocksChk, els.showLabelsChk, els.showOrderChk].forEach((c) =>
  c.addEventListener("change", syncOverlayClasses)
);

els.regionToolBtn.addEventListener("click", () => {
  state.regionMode = !state.regionMode;
  els.regionToolBtn.classList.toggle("active", state.regionMode);
  syncOverlayClasses();
});

els.closeRegionModal.addEventListener("click", () => els.regionModal.classList.add("hidden"));
els.copyRegionBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(els.regionResultText.value);
});
els.insertRegionBlockBtn.addEventListener("click", () => {
  const page = state.doc?.pages[state.lastRegionPageIdx];
  if (!page) return;
  page.blocks.push({
    id: `p${page.page_num}_region_${Date.now()}`,
    label: "Text",
    bbox: state.lastRegionBbox || [0, 0, 0, 0],
    text: els.regionResultText.value,
    conf: 1.0,
  });
  els.regionModal.classList.add("hidden");
  els.pagesContainer.innerHTML = "";
  state.doc.pages.forEach((p, idx) => els.pagesContainer.appendChild(renderPageCard(p, idx)));
  syncOverlayClasses();
});

els.undoBtn.addEventListener("click", () => {
  if (!state.doc || !state.undoStack.length) return;
  const blocksPerPage = JSON.parse(state.undoStack.pop());
  state.doc.pages.forEach((p, i) => {
    if (blocksPerPage[i]) p.blocks = blocksPerPage[i];
  });
  els.undoBtn.disabled = state.undoStack.length === 0;
  els.pagesContainer.innerHTML = "";
  state.doc.pages.forEach((p, idx) => els.pagesContainer.appendChild(renderPageCard(p, idx)));
  syncOverlayClasses();
  els.status.textContent = "Dernière action annulée.";
});

els.replaceAllBtn.addEventListener("click", () => {
  if (!state.doc) return;
  const q = els.findInput.value;
  if (!q) return;
  const rep = els.replaceInput.value;
  pushUndo();
  let count = 0;
  state.doc.pages.forEach((p) => {
    p.blocks.forEach((b) => {
      if (b.text && b.text.includes(q)) {
        const parts = b.text.split(q);
        count += parts.length - 1;
        b.text = parts.join(rep);
      }
    });
  });
  els.pagesContainer.innerHTML = "";
  state.doc.pages.forEach((p, idx) => els.pagesContainer.appendChild(renderPageCard(p, idx)));
  syncOverlayClasses();
  els.status.textContent = `${count} occurrence(s) remplacée(s).`;
});

els.anonymizeBtn.addEventListener("click", async () => {
  if (!state.doc) return;
  pushUndo();
  els.status.textContent = "Anonymisation RGPD en cours...";
  const res = await fetch("/api/anonymize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.doc),
  });
  if (!res.ok) {
    els.status.textContent = "Erreur lors de l'anonymisation.";
    return;
  }
  state.doc = await res.json();
  els.pagesContainer.innerHTML = "";
  state.doc.pages.forEach((p, idx) => els.pagesContainer.appendChild(renderPageCard(p, idx)));
  syncOverlayClasses();
  els.status.textContent = "Emails, téléphones et IBAN masqués (Annuler possible).";
});

els.exportBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  els.exportMenu.classList.toggle("hidden");
});
window.addEventListener("click", () => els.exportMenu.classList.add("hidden"));

document.querySelectorAll(".exp-opt").forEach((btn) => {
  btn.addEventListener("click", async () => {
    els.exportMenu.classList.add("hidden");
    if (!state.doc) return;
    const fmt = btn.dataset.fmt;
    const fallbackExt = fmt === "edited-pdf" ? "pdf" : fmt;
    els.status.textContent = `Export .${fallbackExt} en cours...`;
    const res = await fetch(`/api/export/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.doc),
    });
    if (!res.ok) {
      els.status.textContent = `Erreur export .${fallbackExt}`;
      return;
    }
    const disp = res.headers.get("Content-Disposition") || "";
    const m = disp.match(/filename="([^"]+)"/);
    const base = (state.doc.filename || "document").replace(/\.[^.]+$/, "");
    const fname = m ? m[1] : `${base}.${fallbackExt}`;

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fname;
    a.click();
    URL.revokeObjectURL(url);
    els.status.textContent = `${fname} téléchargé.`;
  });
});
