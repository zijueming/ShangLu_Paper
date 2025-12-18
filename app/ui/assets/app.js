(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  async function fetchJSON(url, opts = {}) {
    const resp = await fetch(url, { cache: "no-store", ...opts });
    const text = await resp.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }
    if (!resp.ok) {
      const msg = data?.error || data?.message || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function initUserBar() {
    const el = $("#userbar");
    if (!el) return;
    try {
      const data = await fetchJSON("/api/me");
      const u = data?.user || {};
      const name = String(u.username || "").trim() || "user";
      const admin = !!u.is_admin;
      const adminLink = admin ? `<a class="btn btn-ghost" href="/admin/">后台</a>` : "";
      el.innerHTML = `<span class="pill">${escapeHtml(name)}</span><a class="btn btn-ghost" href="/account/">账号</a>${adminLink}<a class="btn btn-ghost" href="/logout/">退出</a>`;
    } catch {
      el.innerHTML = `<a class="btn btn-ghost" href="/login/">登录</a>`;
    }
  }

  function initZoomableImages() {
    const zoomables = $$(".zoomable[data-zoom]");
    if (!zoomables.length) return;

    let modal = $("#zoom-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "zoom-modal";
      modal.className = "zoom-modal";
      modal.hidden = true;
      modal.innerHTML = `<div class="zoom-modal__panel" role="dialog" aria-modal="true" aria-label="图片预览">
        <img class="zoom-modal__img" alt="" />
      </div>`;
      document.body.appendChild(modal);
    }

    const img = $(".zoom-modal__img", modal);

    function close() {
      modal.hidden = true;
      document.body.style.overflow = "";
      if (img) img.src = "";
    }

    modal.addEventListener("click", (e) => {
      if (e.target === modal) close();
    });

    document.addEventListener("keydown", (e) => {
      if (!modal.hidden && e.key === "Escape") close();
    });

    zoomables.forEach((el) => {
      el.addEventListener("click", () => {
        const src = el.getAttribute("data-zoom") || el.getAttribute("src") || "";
        if (!src) return;
        if (img) img.src = src;
        modal.hidden = false;
        document.body.style.overflow = "hidden";
      });
    });
  }

  function badge(state) {
    const s = String(state || "unknown");
    const ok = new Set(["analyzed", "translated"]);
    const cls = ok.has(s) ? "ok" : s === "failed" ? "bad" : "warn";
    return `<span class="badge ${cls}">${escapeHtml(s)}</span>`;
  }

  function renderList(items) {
    if (!items || !items.length) return `<div class="hint">未提及</div>`;
    const lis = items.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    return `<ul>${lis}</ul>`;
  }

  function renderSteps(items) {
    if (!items || !items.length) return `<div class="hint">未提及</div>`;
    const lis = items
      .map((x) => {
        const idx = x?.["步骤"] ?? x?.step ?? x?.index ?? "";
        const content = x?.["内容"] ?? x?.content ?? "";
        return `<li><b>${escapeHtml(idx)}</b> ${escapeHtml(content)}</li>`;
      })
      .join("");
    return `<ul>${lis}</ul>`;
  }

  function renderTerms(items) {
    if (!items) return `<div class="hint">未提及</div>`;
    let list = items;
    if (!Array.isArray(list) && typeof list === "object") {
      list = Object.entries(list).map(([term, desc]) => ({ term, desc }));
    }
    if (!Array.isArray(list) || !list.length) return `<div class="hint">未提及</div>`;

    const lis = list
      .map((x) => {
        if (typeof x === "string") return `<li>${escapeHtml(x)}</li>`;
        const term = x?.["术语"] ?? x?.term ?? x?.name ?? x?.["Term"] ?? "";
        const desc = x?.["解释"] ?? x?.desc ?? x?.definition ?? x?.explanation ?? x?.["定义"] ?? "";
        if (!term && !desc) return "";
        if (!desc) return `<li><b>${escapeHtml(term)}</b></li>`;
        return `<li><b>${escapeHtml(term)}</b>：${escapeHtml(desc)}</li>`;
      })
      .filter(Boolean)
      .join("");

    return lis ? `<ul>${lis}</ul>` : `<div class="hint">未提及</div>`;
  }

  function parseJobTime(jobId) {
    const m = /^(\d{8})_(\d{6})/.exec(jobId || "");
    if (!m) return null;
    const y = Number(m[1].slice(0, 4));
    const mo = Number(m[1].slice(4, 6));
    const d = Number(m[1].slice(6, 8));
    const hh = Number(m[2].slice(0, 2));
    const mm = Number(m[2].slice(2, 4));
    const ss = Number(m[2].slice(4, 6));
    const dt = new Date(y, mo - 1, d, hh, mm, ss);
    return Number.isFinite(dt.getTime()) ? dt : null;
  }

  async function initHome() {
    const fileInput = $("#file");
    const btn = $("#btn-import");
    const tbody = $("#jobs-body");
    const q = $("#q");

    let all = [];

    function filtered() {
      const kw = (q?.value || "").trim().toLowerCase();
      if (!kw) return all;
      return all.filter((j) => {
        const tags = (j.tags || []).join(" ");
        const hay = `${j.job_id} ${j.title || ""} ${j.authors || ""} ${j.year || ""} ${tags}`.toLowerCase();
        return hay.includes(kw);
      });
    }

    function render() {
      const rows = filtered()
        .map((j) => {
          const title = j.title || j.job_id;
          const authors = j.authors || "";
          const year = j.year || "";
          const updated = j.updated_at || "";
          const tags = (j.tags || []).slice(0, 6);
          const tagHtml = tags.length
            ? `<div style="margin-top:8px; display:flex; gap:6px; flex-wrap:wrap;">${tags
              .map((t) => `<span class="pill" style="border-color: var(--border); background: var(--bg);">${escapeHtml(t)}</span>`)
              .join("")}</div>`
            : "";
          const tstate = j.translate_state || (j.has_translation ? "translated" : "");
          const tbadge = tstate ? badge(tstate) : `<span class="badge warn">untranslated</span>`;
          return `<tr>
             <td>
               <a class="link" href="/job/${encodeURIComponent(j.job_id)}/">${escapeHtml(title)}</a>
               <div class="hint">${escapeHtml(authors)}</div>
               ${tagHtml}
             </td>
             <td>${escapeHtml(year)}</td>
             <td><div style="display:flex; gap:6px; flex-wrap:wrap;">${badge(j.state)} ${tbadge}</div></td>
             <td>${escapeHtml(updated)}</td>
             <td style="text-align:right; white-space:nowrap;">
               <div style="display:flex; gap:10px; justify-content:flex-end; flex-wrap:wrap;">
                 <a class="btn btn-ghost" href="/job/${encodeURIComponent(j.job_id)}/">打开</a>
                 <button class="btn btn-danger" data-delete="${escapeHtml(j.job_id)}">删除</button>
               </div>
             </td>
           </tr>`;
        })
        .join("");

      tbody.innerHTML =
        rows ||
        `<tr><td colspan="5"><span class="hint">暂无文献，请先导入/解析一篇 PDF。</span></td></tr>`;
    }

    async function loadJobs() {
      const data = await fetchJSON("/api/jobs");
      all = data.jobs || [];
      render();
    }

    async function createJobFromFile(file) {
      if (!file) return;
      if (!/\.pdf$/i.test(file.name || "")) return alert("请选择 PDF 文件");

      btn.disabled = true;
      try {
        const form = new FormData();
        form.append("file", file, file.name || "paper.pdf");
        const data = await fetchJSON("/api/jobs/upload", {
          method: "POST",
          body: form,
        });
        location.href = `/job/${encodeURIComponent(data.job_id)}/`;
      } catch (e) {
        alert(`导入失败：${e.message || e}`);
      } finally {
        btn.disabled = false;
      }
    }

    tbody?.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-delete]");
      if (!btn) return;
      const jobId = btn.dataset.delete;
      if (!jobId) return;
      if (!confirm(`确定删除该文献？\n\n${jobId}\n\n将删除本地解析/分析/翻译结果，无法恢复。`)) return;
      btn.disabled = true;
      try {
        await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/delete`, { method: "POST" });
        await loadJobs();
      } catch (err) {
        alert(`删除失败：${err.message || err}`);
      } finally {
        btn.disabled = false;
      }
    });

    btn?.addEventListener("click", () => fileInput?.click());
    fileInput?.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      // reset so selecting same file again still triggers change
      fileInput.value = "";
      await createJobFromFile(file);
    });
    q?.addEventListener("input", render);

    await loadJobs().catch((e) => {
      tbody.innerHTML = `<tr><td colspan="5"><span class="hint">加载失败：${escapeHtml(e.message || e)}</span></td></tr>`;
    });
  }

  // Global initializers
  initZoomableImages();

  async function initJob() {
    const jobId = document.body.dataset.jobId;
    if (!jobId) return;

    const btnAnalyze = $("#btn-analyze");
    const btnTranslate = $("#btn-translate");
    const btnPdf = $("#btn-pdf");
    const figs = $("#figs");
    const figsInfo = $("#figs-info");
    const figsMore = $("#figs-more");
    const figsToggle = $("#figs-toggle");
    const debug = $("#debug");
    const translateState = $("#translate-state");
    const tagChips = $("#tag-chips");
    const tagSelect = $("#tag-select");
    const tagAdd = $("#tag-add");
    const btnDelete = $("#btn-delete");

    let catalogTags = [];
    let figsLimit = 12;
    let figsMode = "key";
    let currentFigures = [];

    let figModal = null;
    let figModalImg = null;
    let figModalTitle = null;
    let figModalOpen = null;
    let figModalPrev = null;
    let figModalNext = null;
    let figModalClose = null;
    let figModalIndex = 0;

    async function patchTags(payload) {
      await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    }

    function renderTags(tags) {
      const list = Array.isArray(tags) ? tags : [];
      tagChips.innerHTML =
        list
          .map(
            (t) =>
              `<span class="pill" style="gap:6px;">${escapeHtml(t)} <a href="#" data-remove-tag="${escapeHtml(
                t
              )}" style="text-decoration:none; color: var(--muted); font-weight:900;">×</a></span>`
          )
          .join("") || `<span class="hint">暂无标签</span>`;

      $$("[data-remove-tag]", tagChips).forEach((a) => {
        a.addEventListener("click", async (e) => {
          e.preventDefault();
          const t = a.dataset.removeTag;
          if (!t) return;
          try {
            await patchTags({ remove: t });
            await loadMeta();
          } catch (err) {
            alert(`移除标签失败：${err.message || err}`);
          }
        });
      });
    }

    async function loadCatalog() {
      try {
        const data = await fetchJSON("/api/tags/catalog");
        catalogTags = Array.isArray(data.tags) ? data.tags : [];
      } catch {
        catalogTags = [];
      }
    }

    function renderTagOptions(selectedTags) {
      if (!tagSelect) return;
      const selected = new Set((selectedTags || []).map((t) => String(t).toLowerCase()));
      const available = (catalogTags || []).filter((t) => !selected.has(String(t).toLowerCase()));
      const options = available
        .map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`)
        .join("");
      tagSelect.innerHTML = options || `<option value="">（暂无可选标签）</option>`;
      tagSelect.disabled = !available.length;
    }

    async function loadMeta() {
      const meta = await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/meta`);
      $("#state").innerHTML = badge(meta.state) + (meta.error ? ` <span class="badge bad">${escapeHtml(meta.error)}</span>` : "");
      const tstate = meta.translate_state || (meta.has_translation ? "translated" : "");
      translateState.innerHTML =
        (tstate ? badge(tstate) : `<span class="badge warn">untranslated</span>`) +
        (meta.translate_error ? ` <span class="badge bad" title="${escapeHtml(meta.translate_error)}">翻译错误</span>` : "");
      if (debug) debug.textContent = JSON.stringify(meta, null, 2);
      if (meta.pdf_local) {
        btnPdf.href = `/${encodeURIComponent(jobId)}/${encodeURIComponent(meta.pdf_local)}`;
        btnPdf.style.display = "";
      }
      renderTags(meta.tags || []);
      renderTagOptions(meta.tags || []);
      if (btnTranslate) btnTranslate.disabled = meta.translate_state === "translating";
      return meta;
    }

    async function loadAnalysis() {
      try {
        return await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/analysis`);
      } catch {
        return null;
      }
    }

    function renderAnalysis(a) {
      if (!a) {
        $("#paper-title").textContent = "未生成分析（可点击“重新分析”）";
        $("#paper-meta").textContent = "";
        $("#sec-abs").textContent = "未生成分析";
        $("#sec-conc").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-novel").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-method").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-lim").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-steps").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-char").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-insight").innerHTML = `<div class="hint">未生成分析</div>`;
        $("#sec-terms").innerHTML = `<div class="hint">未生成分析</div>`;
        return;
      }

      const title = a.title || a["标题"] || a["论文标题"] || a["paper_title"] || "";
      const authors = a.authors || a["作者"] || "";
      $("#paper-title").textContent = title || "（未提取标题）";
      $("#paper-meta").textContent = authors;

      $("#sec-abs").textContent = a["摘要"] || a.abstract || "未提及";
      $("#sec-conc").innerHTML = renderList(a["主要结论"] || a.main_conclusions);
      $("#sec-novel").innerHTML = renderList(a["创新点"] || a.innovations);
      $("#sec-method").innerHTML = renderList(a["实验方法"] || a.methods);
      $("#sec-lim").innerHTML = renderList(a["不足"] || a.limitations);
      $("#sec-steps").innerHTML = renderSteps(a["实验详细步骤"] || a.experimental_steps);
      $("#sec-char").innerHTML = renderList(a["表征方法"] || a.characterization_methods);
      $("#sec-insight").innerHTML = renderList(a["研究启发"] || a.insights);
      $("#sec-terms").innerHTML = renderTerms(a["术语解释"] || a.terms || a.glossary);
    }

    function ensureFigureModal() {
      if (figModal) return;
      figModal = document.createElement("div");
      figModal.id = "fig-modal";
      figModal.className = "fig-modal";
      figModal.innerHTML = `
        <div class="fig-modal__panel" role="dialog" aria-modal="true">
          <div class="fig-modal__header">
            <div id="fig-modal-title" class="fig-modal__title"></div>
            <div style="display:flex; gap:8px; align-items:center;">
              <a id="fig-modal-open" class="btn btn-ghost" target="_blank" rel="noreferrer">新窗口</a>
              <button id="fig-modal-close" class="btn btn-ghost" type="button">关闭</button>
            </div>
          </div>
          <div class="fig-modal__body">
            <button id="fig-modal-prev" class="btn btn-ghost fig-modal__nav" type="button">←</button>
            <img id="fig-modal-img" alt="figure" />
            <button id="fig-modal-next" class="btn btn-ghost fig-modal__nav" type="button">→</button>
          </div>
        </div>
      `;
      document.body.appendChild(figModal);

      figModalImg = $("#fig-modal-img", figModal);
      figModalTitle = $("#fig-modal-title", figModal);
      figModalOpen = $("#fig-modal-open", figModal);
      figModalPrev = $("#fig-modal-prev", figModal);
      figModalNext = $("#fig-modal-next", figModal);
      figModalClose = $("#fig-modal-close", figModal);

      const close = () => closeFigureModal();

      figModal.addEventListener("click", (e) => {
        if (e.target === figModal) close();
      });
      figModalClose?.addEventListener("click", close);
      figModalPrev?.addEventListener("click", () => openFigureModal(figModalIndex - 1));
      figModalNext?.addEventListener("click", () => openFigureModal(figModalIndex + 1));

      document.addEventListener("keydown", (e) => {
        if (!figModal?.classList.contains("open")) return;
        if (e.key === "Escape") return close();
        if (e.key === "ArrowLeft") return openFigureModal(figModalIndex - 1);
        if (e.key === "ArrowRight") return openFigureModal(figModalIndex + 1);
      });
    }

    function prettyFileName(url) {
      try {
        const raw = String(url || "").split("?")[0].split("#")[0];
        const name = raw.split("/").pop() || "";
        return decodeURIComponent(name);
      } catch {
        return String(url || "");
      }
    }

    function openFigureModal(index) {
      if (!currentFigures.length) return;
      const idx = Math.max(0, Math.min(currentFigures.length - 1, Number(index) || 0));
      ensureFigureModal();
      figModalIndex = idx;
      const url = currentFigures[idx];
      if (figModalImg) figModalImg.src = url;
      if (figModalOpen) figModalOpen.href = url;
      if (figModalTitle) figModalTitle.textContent = `${idx + 1}/${currentFigures.length} ${prettyFileName(url)}`;
      if (figModalPrev) figModalPrev.disabled = idx <= 0;
      if (figModalNext) figModalNext.disabled = idx >= currentFigures.length - 1;
      figModal.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function closeFigureModal() {
      if (!figModal) return;
      figModal.classList.remove("open");
      document.body.style.overflow = "";
    }

    function renderFigures(list) {
      if (!figs) return;
      currentFigures = Array.isArray(list) ? list : [];
      if (!currentFigures.length) {
        figs.textContent = "暂无图片";
        return;
      }
      figs.innerHTML = `<div class="figs">${currentFigures
        .map(
          (url, idx) =>
            `<a href="${url}" target="_blank" rel="noreferrer" data-fig-idx="${idx}" title="${escapeHtml(prettyFileName(url))}"><img src="${url}" loading="lazy" /></a>`
        )
        .join("")}</div>`;

      $$("[data-fig-idx]", figs).forEach((a) => {
        a.addEventListener("click", (e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
          e.preventDefault();
          openFigureModal(Number(a.dataset.figIdx || 0));
        });
      });
    }

    async function loadFigures() {
      if (!figs) return;
      if (figsMore) figsMore.disabled = true;
      if (figsToggle) figsToggle.disabled = true;

      const qs = new URLSearchParams();
      qs.set("limit", String(figsLimit));
      qs.set("mode", figsMode);
      const data = await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/figures?${qs.toString()}`);
      const list = Array.isArray(data.figures) ? data.figures : [];
      const total = Number(data.total || list.length) || list.length;
      figsMode = data.mode === "all" ? "all" : "key";

      renderFigures(list);

      if (figsInfo) figsInfo.textContent = total > 0 ? `${list.length}/${total}` : "";
      if (figsMore) figsMore.disabled = !total || list.length >= total;
      if (figsToggle) {
        figsToggle.textContent = figsMode === "all" ? "仅关键" : "全部图片";
        figsToggle.disabled = !total;
      }
    }

    figsMore?.addEventListener("click", async () => {
      figsLimit = Math.min(400, Math.max(8, figsLimit * 2));
      await loadFigures().catch(() => {
        figs.textContent = "加载失败";
      });
    });

    figsToggle?.addEventListener("click", async () => {
      figsMode = figsMode === "all" ? "key" : "all";
      figsLimit = Math.min(400, Math.max(8, figsLimit));
      await loadFigures().catch(() => {
        figs.textContent = "加载失败";
      });
    });

    async function pollUntilDone() {
      const active = new Set(["queued", "parsing", "parsed", "analyzing"]);
      for (let i = 0; i < 360; i++) {
        const meta = await loadMeta();
        if (!active.has(meta.state)) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    async function pollTranslateUntilDone() {
      const active = new Set(["translating"]);
      for (let i = 0; i < 360; i++) {
        const meta = await loadMeta();
        if (!active.has(meta.translate_state)) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    async function requestAnalyze() {
      btnAnalyze.disabled = true;
      try {
        await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/analyze`, { method: "POST" });
        await pollUntilDone();
        renderAnalysis(await loadAnalysis());
      } catch (e) {
        alert(`请求失败：${e.message || e}`);
      } finally {
        btnAnalyze.disabled = false;
      }
    }

    async function requestTranslate() {
      if (!btnTranslate) return;
      btnTranslate.disabled = true;
      try {
        await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/translate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lang: "zh-CN" }),
        });
        await pollTranslateUntilDone();
      } catch (e) {
        alert(`翻译失败：${e.message || e}`);
      } finally {
        btnTranslate.disabled = false;
      }
    }

    btnAnalyze?.addEventListener("click", requestAnalyze);
    btnTranslate?.addEventListener("click", requestTranslate);
    btnDelete?.addEventListener("click", async () => {
      if (!confirm(`确定删除该文献？\n\n${jobId}\n\n将删除本地解析/分析/翻译结果，无法恢复。`)) return;
      btnDelete.disabled = true;
      try {
        await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/delete`, { method: "POST" });
        location.href = "/";
      } catch (err) {
        alert(`删除失败：${err.message || err}`);
      } finally {
        btnDelete.disabled = false;
      }
    });
    tagAdd?.addEventListener("click", async () => {
      const t = (tagSelect?.value || "").trim();
      if (!t) return;
      try {
        await patchTags({ add: t });
        await loadMeta();
      } catch (err) {
        alert(`添加标签失败：${err.message || err}`);
      }
    });

    await loadCatalog();

    await loadFigures().catch(() => {
      figs.textContent = "加载失败";
    });
    const meta = await loadMeta().catch(() => ({}));
    renderAnalysis(await loadAnalysis());
    const active = new Set(["queued", "parsing", "parsed", "analyzing"]);
    if (active.has(meta.state)) {
      await pollUntilDone();
      renderAnalysis(await loadAnalysis());
    }
  }

  async function initWeekly() {
    const startEl = $("#week-start");
    const endEl = $("#week-end");
    const btnFilter = $("#btn-filter");
    const listEl = $("#paper-list");
    const pickedEl = $("#picked");
    const btnGen = $("#btn-generate");
    const toggleAI = $("#use-ai");
    const taWork = $("#extra-work");
    const taProblems = $("#problems");
    const taPlan = $("#next-plan");
    const out = $("#weekly-out");
    const reportsEl = $("#weekly-reports");
    const openLink = $("#weekly-open");

    let jobs = [];
    const picked = new Set();

    function setDefaults() {
      const now = new Date();
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const start = new Date(end);
      start.setDate(start.getDate() - 7);
      const toISO = (d) => d.toISOString().slice(0, 10);
      if (startEl && !startEl.value) startEl.value = toISO(start);
      if (endEl && !endEl.value) endEl.value = toISO(end);
    }

    function renderPicked() {
      pickedEl.textContent = `已选择文献（${picked.size}）`;
    }

    function renderListUI() {
      const rows = jobs
        .map((j) => {
          const id = j.job_id;
          const title = j.title || id;
          const authors = j.authors || "";
          const disabled = !j.has_analysis || j.state !== "analyzed";
          const checked = picked.has(id) ? "checked" : "";
          const dis = disabled ? "disabled" : "";
          const tip = disabled ? `<div class="hint">需要先完成分析</div>` : `<div class="hint">${escapeHtml(authors)}</div>`;
          const activeClass = picked.has(id) ? "border-brand shadow-sm" : "";
          return `<label class="${activeClass}" style="display:block; padding:12px 14px; border:1.5px solid var(--border); border-radius:var(--radius); background:var(--card); margin:12px 0; transition: var(--transition); cursor: pointer;">
            <div style="display:flex; gap:12px; align-items:flex-start;">
              <input type="checkbox" data-id="${escapeHtml(id)}" ${checked} ${dis} style="margin-top:4px; accent-color: var(--brand);" />
              <div style="flex:1">
                <div style="font-weight:800; line-height:1.35">${escapeHtml(title)}</div>
                ${tip}
              </div>
              <div>${badge(j.state)}</div>
            </div>
          </label>`;
        })
        .join("");

      listEl.innerHTML = rows || `<div class="hint">暂无文献</div>`;
      $$("#paper-list input[type=checkbox]").forEach((cb) => {
        cb.addEventListener("change", () => {
          const id = cb.dataset.id;
          if (!id) return;
          if (cb.checked) picked.add(id);
          else picked.delete(id);
          renderPicked();
        });
      });
      renderPicked();
    }

    async function loadJobs() {
      const start = startEl.value;
      const end = endEl.value;
      const qs = new URLSearchParams();
      if (start) qs.set("start", start);
      if (end) qs.set("end", end);
      const data = await fetchJSON(`/api/jobs?${qs.toString()}`);
      jobs = data.jobs || [];
      // Reset invalid selections
      const allowed = new Set(jobs.filter((j) => j.has_analysis && j.state === "analyzed").map((j) => j.job_id));
      for (const id of Array.from(picked)) if (!allowed.has(id)) picked.delete(id);
      renderListUI();
    }

    async function loadReports() {
      const data = await fetchJSON("/api/weekly/list");
      const items = data.reports || [];
      if (!items.length) {
        reportsEl.innerHTML = `<div class="hint">暂无周报</div>`;
        return;
      }
      reportsEl.innerHTML = items
        .map((r) => {
          const id = r.report_id;
          const title = `${r.start_date || ""} ~ ${r.end_date || ""}`;
          const tag = r.use_ai ? `<span class="pill">AI</span>` : `<span class="pill">模板</span>`;
          return `<div style="display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 12px; border:1px solid var(--border); border-radius:14px; background:rgba(255,255,255,.86); margin:10px 0;">
            <a class="link" href="#" data-report="${escapeHtml(id)}">${escapeHtml(title)}</a>
            ${tag}
          </div>`;
        })
        .join("");

      $$("[data-report]", reportsEl).forEach((a) => {
        a.addEventListener("click", async (e) => {
          e.preventDefault();
          const id = a.dataset.report;
          if (!id) return;
          try {
            const rep = await fetchJSON(`/api/weekly/${encodeURIComponent(id)}`);
            out.value = rep.markdown || "";
            openLink.href = rep.open_url || "#";
            openLink.style.display = rep.open_url ? "" : "none";
          } catch (err) {
            alert(`读取周报失败：${err.message || err}`);
          }
        });
      });
    }

    async function generate() {
      const start = startEl.value;
      const end = endEl.value;
      if (!start || !end) return alert("请选择日期范围");
      if (!picked.size) return alert("请选择至少 1 篇已分析的文献");

      btnGen.disabled = true;
      out.value = "生成中…";
      try {
        const body = {
          start_date: start,
          end_date: end,
          job_ids: Array.from(picked),
          extra_work: taWork.value || "",
          problems: taProblems.value || "",
          next_plan: taPlan.value || "",
          use_ai: !!toggleAI.checked,
        };
        const rep = await fetchJSON("/api/weekly/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        out.value = rep.markdown || "";
        openLink.href = rep.open_url || "#";
        openLink.style.display = rep.open_url ? "" : "none";
        await loadReports();
      } catch (e) {
        out.value = "";
        alert(`生成失败：${e.message || e}`);
      } finally {
        btnGen.disabled = false;
      }
    }

    btnFilter?.addEventListener("click", () => loadJobs().catch((e) => alert(e.message || e)));
    btnGen?.addEventListener("click", generate);

    setDefaults();
    await Promise.all([loadJobs().catch(() => { }), loadReports().catch(() => { })]);
  }

  async function initTags() {
    const listEl = $("#tags-list");
    const jobsEl = $("#tags-jobs");
    const q = $("#q");
    const newTag = $("#new-tag");
    const btnNewTag = $("#btn-new-tag");

    let tags = [];
    let selected = "";

    function renderTags() {
      const kw = (q?.value || "").trim().toLowerCase();
      const filtered = kw ? tags.filter((t) => String(t.tag || "").toLowerCase().includes(kw)) : tags;
      filtered.forEach((t) => {
        const isActive = t.tag === selected;
        const activeStyle = isActive ? "border-color: var(--brand); box-shadow: var(--shadow-sm); transform: translateY(-1px);" : "";
        const html = `<div data-tag="${escapeHtml(t.tag)}" style="cursor:pointer; padding:12px 16px; border:1px solid var(--border); border-radius:var(--radius); background:var(--card); margin:12px 0; display:flex; justify-content:space-between; gap:10px; transition: var(--transition); ${activeStyle}">
              <div style="font-weight:700; color: ${isActive ? 'var(--brand)' : 'inherit'}">${escapeHtml(t.tag)}</div>
              <span class="pill" style="${isActive ? 'background: var(--brand); color: #fff; border:none;' : ''}">${escapeHtml(t.count)}</span>
            </div>`;
        listEl.insertAdjacentHTML('beforeend', html);
      });

      $$("[data-tag]", listEl).forEach((row) => {
        row.addEventListener("click", () => {
          selected = row.dataset.tag || "";
          renderTags();
          renderJobs();
        });
      });
    }

    function renderJobs() {
      const item = tags.find((t) => t.tag === selected);
      const jobs = item?.jobs || [];
      if (!selected) {
        jobsEl.innerHTML = `<div class="hint">请选择一个标签</div>`;
        return;
      }
      if (!jobs.length) {
        jobsEl.innerHTML = `<div class="hint">该标签下暂无文献</div>`;
        return;
      }
      jobsEl.innerHTML = jobs
        .map((j) => {
          const title = j.title || j.job_id;
          const authors = j.authors || "";
          return `<div style="padding:10px 12px; border:1px solid var(--border); border-radius:14px; background:rgba(255,255,255,.86); margin:10px 0;">
            <a class="link" href="/job/${encodeURIComponent(j.job_id)}/">${escapeHtml(title)}</a>
            <div class="hint">${escapeHtml(authors)}</div>
          </div>`;
        })
        .join("");
    }

    async function load() {
      const data = await fetchJSON("/api/tags");
      tags = data.tags || [];
      if (!selected && tags.length) selected = tags[0].tag;
      renderTags();
      renderJobs();
    }

    async function createTag() {
      const t = (newTag?.value || "").trim();
      if (!t) return;
      if (btnNewTag) btnNewTag.disabled = true;
      try {
        await fetchJSON("/api/tags/catalog", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ add: t }),
        });
        if (newTag) newTag.value = "";
        await load();
      } catch (e) {
        alert(`新建标签失败：${e.message || e}`);
      } finally {
        if (btnNewTag) btnNewTag.disabled = false;
      }
    }

    q?.addEventListener("input", renderTags);
    btnNewTag?.addEventListener("click", createTag);
    newTag?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        createTag();
      }
    });
    await load().catch((e) => {
      listEl.innerHTML = `<div class="hint">加载失败：${escapeHtml(e.message || e)}</div>`;
    });
  }

  async function initTranslate() {
    const tbody = $("#translate-body");
    const q = $("#q");
    let all = [];

    function filtered() {
      const kw = (q?.value || "").trim().toLowerCase();
      if (!kw) return all;
      return all.filter((j) => {
        const tags = (j.tags || []).join(" ");
        const hay = `${j.job_id} ${j.title || ""} ${j.authors || ""} ${j.year || ""} ${tags}`.toLowerCase();
        return hay.includes(kw);
      });
    }

    function tBadge(j) {
      const t = j.translate_state || (j.has_translation ? "translated" : "");
      return t ? badge(t) : `<span class="badge warn">untranslated</span>`;
    }

    function render() {
      const rows = filtered()
        .map((j) => {
          const id = j.job_id;
          const title = j.title || id;
          const authors = j.authors || "";
          const canTranslate = !["queued", "parsing"].includes(j.state || "") && j.translate_state !== "translating";
          const translateBtn = canTranslate
            ? `<button class="btn btn-primary" data-translate="${escapeHtml(id)}">翻译</button>`
            : `<button class="btn" disabled>翻译</button>`;

          const viewBtn = `<a class="btn" href="/view/${encodeURIComponent(id)}/" target="_blank">查看</a>`;
          const openBtn = `<a class="btn btn-ghost" href="/job/${encodeURIComponent(id)}/">打开</a>`;
          return `<tr>
            <td>
              <a class="link" href="/job/${encodeURIComponent(id)}/">${escapeHtml(title)}</a>
              <div class="hint">${escapeHtml(authors)}</div>
            </td>
            <td>${badge(j.state)}</td>
            <td>${tBadge(j)}</td>
            <td style="text-align:right; white-space:nowrap; display:flex; gap:10px; justify-content:flex-end;">
              ${translateBtn}
              ${viewBtn}
              ${openBtn}
            </td>
          </tr>`;
        })
        .join("");

      tbody.innerHTML = rows || `<tr><td colspan="4"><span class="hint">暂无文献</span></td></tr>`;
    }

    async function poll(jobId) {
      for (let i = 0; i < 360; i++) {
        const meta = await fetchJSON(`/api/jobs/${encodeURIComponent(jobId)}/meta`);
        if (meta.translate_state !== "translating") return;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    async function loadJobs() {
      const data = await fetchJSON("/api/jobs");
      all = data.jobs || [];
      render();
    }

    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-translate]");
      if (!btn) return;
      const id = btn.dataset.translate;
      if (!id) return;
      btn.disabled = true;
      btn.textContent = "翻译中…";
      try {
        await fetchJSON(`/api/jobs/${encodeURIComponent(id)}/translate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lang: "zh-CN" }),
        });
        await poll(id);
        await loadJobs();
      } catch (err) {
        alert(`翻译失败：${err.message || err}`);
        await loadJobs();
      }
    });

    q?.addEventListener("input", render);
    await loadJobs().catch((e) => {
      tbody.innerHTML = `<tr><td colspan="4"><span class="hint">加载失败：${escapeHtml(e.message || e)}</span></td></tr>`;
    });
  }

  async function initDraw() {
    const promptEl = $("#draw-prompt");
    const polishedEl = $("#draw-polished");
    const useAiEl = $("#draw-use-ai");
    const urlsEl = $("#draw-urls");
    const hostEl = $("#draw-host");
    const modelEl = $("#draw-model");
    const ratioEl = $("#draw-ratio");
    const sizeEl = $("#draw-size");

    const btnPolish = $("#draw-polish");
    const btnSubmit = $("#draw-submit");
    const btnClear = $("#draw-clear");
    const tipEl = $("#draw-tip");

    const statusEl = $("#draw-status");
    const outputEl = $("#draw-output");
    const historyEl = $("#draw-history");
    const btnRefresh = $("#draw-refresh");

    let activeId = "";
    let historyItems = [];
    let currentResultUrls = [];

    let imgModal = null;
    let imgModalImg = null;
    let imgModalTitle = null;
    let imgModalOpen = null;
    let imgModalPrev = null;
    let imgModalNext = null;
    let imgModalClose = null;
    let imgModalIndex = 0;

    function isImageUrl(u) {
      const s = String(u || "").split("?")[0].split("#")[0].toLowerCase();
      return [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".avif"].some((ext) => s.endsWith(ext));
    }

    function pickImageUrl(localUrl, remoteUrl) {
      const local = String(localUrl || "").trim();
      const remote = String(remoteUrl || "").trim();
      if (local && isImageUrl(local)) return local;
      if (remote && isImageUrl(remote)) return remote;
      return local || remote || "";
    }

    function drawBadge(state) {
      const s = String(state || "unknown");
      const ok = new Set(["succeeded"]);
      const cls = ok.has(s) ? "ok" : s === "failed" ? "bad" : "warn";
      return `<span class="badge ${cls}">${escapeHtml(s)}</span>`;
    }

    function setTip(msg) {
      if (tipEl) tipEl.textContent = msg || "";
    }

    function renderStatus(meta) {
      if (!statusEl) return;
      const state = meta?.state || "unknown";
      const progress = Number(meta?.progress || 0);
      const err = meta?.error || "";
      const reason = meta?.failure_reason || "";
      const warn = meta?.warning || "";
      const bar = `<div class="progress" style="margin-top:8px;"><div class="progress-bar" style="width:${Math.max(
        0,
        Math.min(100, progress)
      )}%"></div></div>`;
      const extra = err || reason ? `<div class="hint" style="margin-top:8px; color: var(--bad);">${escapeHtml(err || reason)}</div>` : "";
      const warnHtml = warn ? `<div class="hint" style="margin-top:8px; color: var(--warn);">${escapeHtml(warn)}</div>` : "";
      statusEl.innerHTML = `${drawBadge(state)} <span class="hint">进度 ${escapeHtml(progress)}</span>${bar}${warnHtml}${extra}`;
    }

    function renderOutput(meta) {
      if (!outputEl) return;
      const promptFinal = String(meta?.prompt_final || "");
      const promptPolished = String(meta?.prompt_polished || "");
      const results = Array.isArray(meta?.results) ? meta.results : [];
      currentResultUrls = [];

      const promptBox = promptFinal
        ? `<details class="debug-details" style="margin-bottom:12px;">
            <summary class="card-title" style="margin:0;">使用的提示词</summary>
            <pre class="codebox">${escapeHtml(promptFinal)}</pre>
          </details>`
        : "";

      const polishedBox =
        promptPolished && promptPolished !== promptFinal
          ? `<details class="debug-details" style="margin-bottom:12px;">
              <summary class="card-title" style="margin:0;">AI 润色结果</summary>
              <pre class="codebox">${escapeHtml(promptPolished)}</pre>
            </details>`
          : "";

      const imgs = results
        .map((r) => {
          const url = pickImageUrl(r?.local_url, r?.url);
          if (!url) return "";
          const idx = currentResultUrls.length;
          currentResultUrls.push(url);
          const content = String(r?.content || "").trim();
          const cap = content ? `<div class="hint" style="margin-top:6px;">${escapeHtml(content)}</div>` : "";
          const media = isImageUrl(url)
            ? `<a href="${url}" target="_blank" rel="noreferrer" data-draw-img-idx="${idx}"><img src="${url}" style="width:100%; max-height:520px; object-fit:contain; border:1px solid var(--border); border-radius: var(--radius); background:#fff;" /></a>`
            : `<a class="link" href="${url}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a>`;
          return `<div style="margin-bottom:14px;">
            ${media}
            ${cap}
          </div>`;
        })
        .filter(Boolean)
        .join("");

      outputEl.innerHTML = `${promptBox}${polishedBox}${imgs || `<div class="hint">暂无结果</div>`}`;
    }

    function ensureImgModal() {
      if (imgModal) return;
      imgModal = document.createElement("div");
      imgModal.id = "draw-img-modal";
      imgModal.className = "fig-modal";
      imgModal.innerHTML = `
        <div class="fig-modal__panel" role="dialog" aria-modal="true">
          <div class="fig-modal__header">
            <div id="draw-img-modal-title" class="fig-modal__title"></div>
            <div style="display:flex; gap:8px; align-items:center;">
              <a id="draw-img-modal-open" class="btn btn-ghost" target="_blank" rel="noreferrer">新窗口</a>
              <button id="draw-img-modal-close" class="btn btn-ghost" type="button">关闭</button>
            </div>
          </div>
          <div class="fig-modal__body">
            <button id="draw-img-modal-prev" class="btn btn-ghost fig-modal__nav" type="button">←</button>
            <img id="draw-img-modal-img" alt="" />
            <button id="draw-img-modal-next" class="btn btn-ghost fig-modal__nav" type="button">→</button>
          </div>
        </div>`;
      document.body.appendChild(imgModal);

      imgModalImg = $("#draw-img-modal-img", imgModal);
      imgModalTitle = $("#draw-img-modal-title", imgModal);
      imgModalOpen = $("#draw-img-modal-open", imgModal);
      imgModalPrev = $("#draw-img-modal-prev", imgModal);
      imgModalNext = $("#draw-img-modal-next", imgModal);
      imgModalClose = $("#draw-img-modal-close", imgModal);

      const close = () => closeImgModal();
      imgModalClose?.addEventListener("click", close);
      imgModal.addEventListener("click", (e) => {
        if (e.target === imgModal) close();
      });
      imgModalPrev?.addEventListener("click", () => openImgModal(imgModalIndex - 1));
      imgModalNext?.addEventListener("click", () => openImgModal(imgModalIndex + 1));

      document.addEventListener("keydown", (e) => {
        if (!imgModal?.classList.contains("open")) return;
        if (e.key === "Escape") return close();
        if (e.key === "ArrowLeft") return openImgModal(imgModalIndex - 1);
        if (e.key === "ArrowRight") return openImgModal(imgModalIndex + 1);
      });
    }

    function openImgModal(index) {
      if (!currentResultUrls.length) return;
      const idx = Math.max(0, Math.min(currentResultUrls.length - 1, Number(index) || 0));
      ensureImgModal();
      imgModalIndex = idx;
      const url = currentResultUrls[idx];
      if (imgModalImg) imgModalImg.src = url;
      if (imgModalOpen) imgModalOpen.href = url;
      if (imgModalTitle) imgModalTitle.textContent = `${idx + 1}/${currentResultUrls.length}`;
      if (imgModalPrev) imgModalPrev.disabled = idx <= 0;
      if (imgModalNext) imgModalNext.disabled = idx >= currentResultUrls.length - 1;
      imgModal.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function closeImgModal() {
      if (!imgModal) return;
      imgModal.classList.remove("open");
      document.body.style.overflow = "";
    }

    async function loadOne(id) {
      const meta = await fetchJSON(`/api/draw/${encodeURIComponent(id)}`);
      renderStatus(meta);
      renderOutput(meta);
      return meta;
    }

    async function poll(id) {
      for (let i = 0; i < 600; i++) {
        const meta = await loadOne(id);
        const state = String(meta?.state || "");
        if (["succeeded", "failed"].includes(state)) return meta;
        await new Promise((r) => setTimeout(r, 1500));
      }
      return null;
    }

    function renderHistory(items) {
      if (!historyEl) return;
      const list = Array.isArray(items) ? items : [];
      if (!list.length) {
        historyEl.innerHTML = `<div class="hint">暂无记录</div>`;
        return;
      }

      historyEl.innerHTML = list
        .map((x) => {
          const id = x.id || "";
          const state = x.state || "";
          const updated = x.updated_at || "";
          const model = x.model || "";
          const title = (x.prompt_final || x.prompt || id || "").trim();
          const short = title.length > 26 ? title.slice(0, 26) + "…" : title;
          const active = id && id === activeId ? "border-color: var(--brand); box-shadow: var(--shadow-sm); transform: translateY(-1px);" : "";
          const delBtn = id
            ? `<button class="btn btn-ghost" data-draw-delete="${escapeHtml(
              id
            )}" type="button" style="padding:4px 10px; font-size:12px;">删除</button>`
            : "";
          return `<div data-draw-id="${escapeHtml(id)}" style="display:block; cursor:pointer; padding:12px 16px; border:1.5px solid var(--border); border-radius:var(--radius); background:var(--card); margin:12px 0; transition: var(--transition); ${active}">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
              <div style="font-weight:800; line-height:1.3;">${escapeHtml(short || id)}</div>
              <div style="display:flex; gap:8px; align-items:center;">
                <div>${drawBadge(state)}</div>
                ${delBtn}
              </div>
            </div>
            <div class="hint" style="margin-top:6px;">${escapeHtml(model)} · ${escapeHtml(updated)}</div>
          </div>`;
        })
        .join("");
    }

    async function loadHistory(opts = {}) {
      const data = await fetchJSON("/api/draw/list?limit=50");
      historyItems = Array.isArray(data.drawings) ? data.drawings : [];
      const ids = new Set(historyItems.map((x) => x?.id).filter(Boolean));
      const autoSelect = !!opts.autoSelect;
      const shouldPick = autoSelect && historyItems.length && (!activeId || !ids.has(activeId));
      if (shouldPick) activeId = String(historyItems[0]?.id || "").trim();
      renderHistory(historyItems);
      if (shouldPick && activeId) {
        await loadOne(activeId).catch(() => { });
      }
    }

    btnRefresh?.addEventListener("click", () => loadHistory().catch((e) => alert(`加载失败：${e.message || e}`)));

    historyEl?.addEventListener("click", async (e) => {
      const target = e.target instanceof Element ? e.target : null;
      if (!target) return;

      const del = target.closest("[data-draw-delete]");
      if (del) {
        e.preventDefault();
        e.stopPropagation();
        const id = String(del.dataset.drawDelete || "").trim();
        if (!id) return;
        if (!confirm(`确定删除这条历史记录？\n\n${id}\n\n将删除本地保存的图片与 meta.json，无法恢复。`)) return;
        del.disabled = true;
        try {
          await fetchJSON(`/api/draw/${encodeURIComponent(id)}/delete`, { method: "POST" });
          if (activeId === id) {
            activeId = "";
            if (statusEl) statusEl.textContent = "未开始";
            if (outputEl) outputEl.innerHTML = "";
          }
          await loadHistory({ autoSelect: true }).catch(() => { });
        } catch (err) {
          alert(`删除失败：${err.message || err}`);
        } finally {
          del.disabled = false;
        }
        return;
      }

      const item = target.closest("[data-draw-id]");
      if (!item) return;
      const id = String(item.dataset.drawId || "").trim();
      if (!id) return;
      activeId = id;
      await loadOne(id).catch((err) => alert(`加载失败：${err.message || err}`));
      renderHistory(historyItems);
    });

    outputEl?.addEventListener("click", (e) => {
      const target = e.target instanceof Element ? e.target : null;
      if (!target) return;
      const a = target.closest("[data-draw-img-idx]");
      if (!a) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      openImgModal(Number(a.dataset.drawImgIdx || 0));
    });

    btnClear?.addEventListener("click", () => {
      if (promptEl) promptEl.value = "";
      if (polishedEl) polishedEl.value = "";
      if (urlsEl) urlsEl.value = "";
      if (statusEl) statusEl.textContent = "未开始";
      if (outputEl) outputEl.innerHTML = "";
      activeId = "";
      setTip("");
      loadHistory().catch(() => { });
    });

    btnPolish?.addEventListener("click", async () => {
      const raw = (promptEl?.value || "").trim();
      if (!raw) return alert("请先输入提示词");
      if (btnPolish) btnPolish.disabled = true;
      setTip("润色中…");
      try {
        const data = await fetchJSON("/api/draw/polish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: raw }),
        });
        if (polishedEl) polishedEl.value = String(data.prompt || "").trim();
        setTip("已润色");
      } catch (e) {
        setTip("");
        alert(`润色失败：${e.message || e}`);
      } finally {
        if (btnPolish) btnPolish.disabled = false;
      }
    });

    btnSubmit?.addEventListener("click", async () => {
      const raw = (promptEl?.value || "").trim();
      const polished = (polishedEl?.value || "").trim();
      if (!raw && !polished) return alert("请输入提示词");

      const host = (hostEl?.value || "").trim();
      const model = (modelEl?.value || "nano-banana-fast").trim();
      const aspectRatio = (ratioEl?.value || "auto").trim();
      const imageSize = (sizeEl?.value || "1K").trim();
      const use_ai = Boolean(useAiEl?.checked) && !polished;
      const urls = (urlsEl?.value || "")
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean);

      if (btnSubmit) btnSubmit.disabled = true;
      setTip("已提交，生成中…");
      if (statusEl) statusEl.textContent = "提交中…";
      if (outputEl) outputEl.innerHTML = "";

      try {
        const data = await fetchJSON("/api/draw/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: raw || polished,
            prompt_override: polished,
            model,
            aspectRatio,
            imageSize,
            urls,
            host,
            use_ai,
          }),
        });
        const id = data.id;
        if (!id) throw new Error("missing id");
        activeId = id;
        await loadHistory().catch(() => { });
        const meta = await poll(id);
        await loadHistory().catch(() => { });
        if (!meta) return;
        if (String(meta.state || "") === "succeeded") setTip("生成成功");
        else setTip("生成失败");
      } catch (e) {
        setTip("");
        alert(`生成失败：${e.message || e}`);
      } finally {
        if (btnSubmit) btnSubmit.disabled = false;
      }
    });

    await loadHistory({ autoSelect: true }).catch(() => {
      if (historyEl) historyEl.textContent = "加载失败";
    });
  }

  class RelationshipGraphView {
    constructor(canvas, tooltipEl, wrapEl) {
      this.canvas = canvas;
      this.tooltipEl = tooltipEl;
      this.wrapEl = wrapEl;
      this.ctx = canvas.getContext("2d");
      this.dpr = Math.max(1, window.devicePixelRatio || 1);
      this.nodes = [];
      this.edges = [];
      this.nodeIndex = new Map();
      this.hoverIndex = -1;
      this.dragIndex = -1;
      this.running = false;
      this.raf = 0;
      this.resizeObserver = null;

      this._bindEvents();
      this.resize();
      if (wrapEl && window.ResizeObserver) {
        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(wrapEl);
      }
    }

    destroy() {
      this.stop();
      try {
        this.resizeObserver?.disconnect();
      } catch { }
    }

    resize() {
      if (!this.wrapEl) return;
      const w = Math.max(10, this.wrapEl.clientWidth || 10);
      const h = Math.max(10, this.wrapEl.clientHeight || 10);
      this.width = w;
      this.height = h;
      this.canvas.width = Math.floor(w * this.dpr);
      this.canvas.height = Math.floor(h * this.dpr);
      this.draw();
    }

    setGraph(graph) {
      const g = graph && typeof graph === "object" ? graph : {};
      const nodesRaw = Array.isArray(g.nodes) ? g.nodes : [];
      const edgesRaw = Array.isArray(g.edges) ? g.edges : [];
      const clustersRaw = Array.isArray(g.clusters) ? g.clusters : [];

      const clusterByNode = new Map();
      clustersRaw.forEach((c, idx) => {
        const ids = Array.isArray(c?.node_ids) ? c.node_ids : [];
        ids.forEach((id) => {
          if (!clusterByNode.has(String(id))) clusterByNode.set(String(id), idx);
        });
      });

      const palette = ["#059669", "#10b981", "#34d399", "#064e3b", "#065f46", "#047857", "#14b8a6", "#0d9488"];
      const colorForCluster = (idx) => palette[Math.abs(Number(idx) || 0) % palette.length];
      const hash = (s) => {
        let h = 0;
        for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
        return h;
      };

      this.nodes = nodesRaw
        .map((n) => {
          const id = String(n?.id || "").trim();
          const title = String(n?.title || id).trim();
          if (!id) return null;
          const tags = Array.isArray(n?.tags) ? n.tags.map((t) => String(t)) : [];
          const clusterIdx = clusterByNode.has(id) ? clusterByNode.get(id) : null;
          const color = clusterIdx != null ? colorForCluster(clusterIdx) : colorForCluster(hash(tags.join("|") || title));
          return {
            id,
            title,
            authors: String(n?.authors || "").trim(),
            year: String(n?.year || "").trim(),
            tags,
            summary: String(n?.summary || "").trim(),
            color,
            x: 0,
            y: 0,
            vx: 0,
            vy: 0,
            fx: 0,
            fy: 0,
            r: 12,
            degree: 0,
            fixed: false,
          };
        })
        .filter(Boolean);

      this.nodeIndex = new Map(this.nodes.map((n, idx) => [n.id, idx]));

      this.edges = edgesRaw
        .map((e) => {
          const a = this.nodeIndex.get(String(e?.source || ""));
          const b = this.nodeIndex.get(String(e?.target || ""));
          if (a == null || b == null || a === b) return null;
          const w = Number(e?.weight || 3) || 3;
          return {
            a,
            b,
            type: String(e?.type || "related"),
            weight: Math.max(1, Math.min(5, Math.round(w))),
            reason: String(e?.reason || "").trim(),
          };
        })
        .filter(Boolean);

      // degrees + radius
      this.nodes.forEach((n) => (n.degree = 0));
      this.edges.forEach((e) => {
        this.nodes[e.a].degree += 1;
        this.nodes[e.b].degree += 1;
      });
      this.nodes.forEach((n) => {
        n.r = Math.max(10, Math.min(24, 10 + n.degree * 1.2));
      });

      // init positions
      const w = this.width || 800;
      const h = this.height || 600;
      const cx = w / 2;
      const cy = h / 2;
      const radius = Math.max(120, Math.min(w, h) * 0.32);
      const nCount = Math.max(1, this.nodes.length);
      this.nodes.forEach((n, i) => {
        const ang = (i / nCount) * Math.PI * 2;
        n.x = cx + Math.cos(ang) * radius + (Math.random() - 0.5) * 12;
        n.y = cy + Math.sin(ang) * radius + (Math.random() - 0.5) * 12;
        n.vx = 0;
        n.vy = 0;
        n.fixed = false;
      });

      this.hoverIndex = -1;
      this.dragIndex = -1;
      this._warmup(Math.min(420, 80 + this.nodes.length * 6));
      this.start();
    }

    start() {
      if (this.running) return;
      this.running = true;
      const step = () => {
        if (!this.running) return;
        this._tick();
        this.draw();
        this.raf = window.requestAnimationFrame(step);
      };
      this.raf = window.requestAnimationFrame(step);
      // Stop auto animation after a short period (still interactive).
      window.setTimeout(() => this.stop(), 2200);
    }

    stop() {
      if (!this.running) return;
      this.running = false;
      if (this.raf) window.cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.draw();
    }

    _warmup(iterations) {
      for (let i = 0; i < iterations; i++) this._tick(true);
    }

    _tick(isWarmup = false) {
      const nodes = this.nodes;
      const edges = this.edges;
      const n = nodes.length;
      if (!n) return;

      const w = this.width || 800;
      const h = this.height || 600;
      const cx = w / 2;
      const cy = h / 2;

      // reset forces
      for (let i = 0; i < n; i++) {
        nodes[i].fx = 0;
        nodes[i].fy = 0;
      }

      // repulsion
      const repulse = 5600;
      for (let i = 0; i < n; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < n; j++) {
          const b = nodes[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          const dist2 = dx * dx + dy * dy + 0.01;
          const inv = 1 / Math.sqrt(dist2);
          dx *= inv;
          dy *= inv;
          const f = repulse / dist2;
          a.fx -= dx * f;
          a.fy -= dy * f;
          b.fx += dx * f;
          b.fy += dy * f;
        }
      }

      // link attraction
      const baseDist = Math.max(80, Math.min(180, Math.min(w, h) * 0.18));
      for (let k = 0; k < edges.length; k++) {
        const e = edges[k];
        const a = nodes[e.a];
        const b = nodes[e.b];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
        const target = baseDist * (1.0 - (e.weight - 3) * 0.08);
        const strength = 0.015 * e.weight;
        const diff = dist - target;
        const fx = (dx / dist) * diff * strength;
        const fy = (dy / dist) * diff * strength;
        a.fx += fx;
        a.fy += fy;
        b.fx -= fx;
        b.fy -= fy;
      }

      // center gravity
      const pull = 0.012;
      for (let i = 0; i < n; i++) {
        const node = nodes[i];
        node.fx += (cx - node.x) * pull;
        node.fy += (cy - node.y) * pull;
      }

      const damping = isWarmup ? 0.82 : 0.88;
      const margin = 18;
      for (let i = 0; i < n; i++) {
        const node = nodes[i];
        if (node.fixed) {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        node.vx = (node.vx + node.fx) * damping;
        node.vy = (node.vy + node.fy) * damping;
        node.x += node.vx;
        node.y += node.vy;
        node.x = Math.max(margin, Math.min(w - margin, node.x));
        node.y = Math.max(margin, Math.min(h - margin, node.y));
      }
    }

    _bindEvents() {
      const toPos = (evt) => {
        const rect = this.canvas.getBoundingClientRect();
        const x = evt.clientX - rect.left;
        const y = evt.clientY - rect.top;
        return { x, y };
      };

      const findNodeAt = (pos) => {
        const x = pos.x;
        const y = pos.y;
        for (let i = this.nodes.length - 1; i >= 0; i--) {
          const n = this.nodes[i];
          const dx = x - n.x;
          const dy = y - n.y;
          if (dx * dx + dy * dy <= (n.r + 3) * (n.r + 3)) return i;
        }
        return -1;
      };

      this.canvas.addEventListener("mousemove", (evt) => {
        const pos = toPos(evt);
        if (this.dragIndex >= 0) {
          const n = this.nodes[this.dragIndex];
          n.x = pos.x;
          n.y = pos.y;
          this.start();
          return;
        }

        const idx = findNodeAt(pos);
        if (idx !== this.hoverIndex) {
          this.hoverIndex = idx;
          this.draw();
        }

        if (idx >= 0) {
          const n = this.nodes[idx];
          const tags = n.tags?.length ? `标签：${n.tags.slice(0, 8).join(", ")}` : "";
          const meta = [n.year, n.authors].filter(Boolean).join(" · ");
          const text = `${n.title}${meta ? `\n${meta}` : ""}${tags ? `\n${tags}` : ""}${n.summary ? `\n\n${n.summary}` : ""}`;
          if (this.tooltipEl) {
            this.tooltipEl.textContent = text;
            this.tooltipEl.style.display = "block";
            const pad = 12;
            const left = Math.min(this.width - 20, Math.max(10, pos.x + pad));
            const top = Math.min(this.height - 20, Math.max(10, pos.y + pad));
            this.tooltipEl.style.left = `${left}px`;
            this.tooltipEl.style.top = `${top}px`;
          }
        } else if (this.tooltipEl) {
          this.tooltipEl.style.display = "none";
        }
      });

      this.canvas.addEventListener("mouseleave", () => {
        this.hoverIndex = -1;
        this.dragIndex = -1;
        if (this.tooltipEl) this.tooltipEl.style.display = "none";
        this.draw();
      });

      this.canvas.addEventListener("mousedown", (evt) => {
        if (evt.button !== 0) return;
        const pos = toPos(evt);
        const idx = findNodeAt(pos);
        if (idx < 0) return;
        const n = this.nodes[idx];
        this.dragIndex = idx;
        n.fixed = true;
        n.x = pos.x;
        n.y = pos.y;
        this.start();
      });

      window.addEventListener("mouseup", () => {
        if (this.dragIndex < 0) return;
        const n = this.nodes[this.dragIndex];
        n.fixed = false;
        this.dragIndex = -1;
        this.start();
      });

      this.canvas.addEventListener("click", (evt) => {
        const pos = toPos(evt);
        const idx = findNodeAt(pos);
        if (idx < 0) return;
        const n = this.nodes[idx];
        window.open(`/job/${encodeURIComponent(n.id)}/`, "_blank");
      });
    }

    draw() {
      const ctx = this.ctx;
      if (!ctx) return;
      const w = this.width || 800;
      const h = this.height || 600;

      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const hovered = this.hoverIndex;
      const adjacent = new Set();
      if (hovered >= 0) {
        this.edges.forEach((e) => {
          if (e.a === hovered) adjacent.add(e.b);
          else if (e.b === hovered) adjacent.add(e.a);
        });
      }

      // edges
      for (let i = 0; i < this.edges.length; i++) {
        const e = this.edges[i];
        const a = this.nodes[e.a];
        const b = this.nodes[e.b];
        const focus = hovered < 0 || e.a === hovered || e.b === hovered;
        ctx.globalAlpha = focus ? 0.55 : 0.12;
        ctx.strokeStyle = "#cbd5e1"; // Slated light gray
        ctx.lineWidth = 1 + (e.weight - 3) * 0.7;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // nodes
      const labelAll = this.nodes.length <= 25;
      const important = new Set(
        this.nodes
          .map((n, idx) => ({ idx, d: n.degree }))
          .sort((a, b) => b.d - a.d)
          .slice(0, 10)
          .map((x) => x.idx)
      );

      for (let i = 0; i < this.nodes.length; i++) {
        const n = this.nodes[i];
        const focus = hovered < 0 || i === hovered || adjacent.has(i);
        ctx.globalAlpha = focus ? 1 : 0.25;
        ctx.fillStyle = n.color;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = "rgba(0,0,0,0.10)";
        ctx.lineWidth = 1;
        ctx.stroke();

        const showLabel = labelAll || important.has(i) || i === hovered;
        if (showLabel) {
          const label = String(n.title || n.id);
          const short = label.length > 16 ? label.slice(0, 16) + "…" : label;
          ctx.globalAlpha = focus ? 0.9 : 0.25;
          ctx.fillStyle = "#212529";
          ctx.font = "500 12px 'Inter', ui-sans-serif, system-ui, -apple-system";
          ctx.textBaseline = "middle";
          ctx.fillText(short, n.x + n.r + 6, n.y);
        }
      }
      ctx.globalAlpha = 1;
    }
  }

  async function initRelationship() {
    const statusEl = $("#rel-status");
    const emptyEl = $("#rel-empty");
    const wrapEl = $("#rel-canvas-wrap");
    const canvas = $("#rel-canvas");
    const tooltip = $("#rel-tooltip");
    const maxEl = $("#rel-max");
    const btnBuild = $("#rel-build");
    const btnBuildBig = $("#rel-build-big");
    const btnRefresh = $("#rel-refresh");

    if (!statusEl || !wrapEl || !canvas) return;

    let view = new RelationshipGraphView(canvas, tooltip, wrapEl);
    let busy = false;

    function setStatus(text) {
      statusEl.textContent = text || "";
    }

    function showEmpty() {
      if (emptyEl) emptyEl.style.display = "";
      wrapEl.style.display = "none";
    }

    function showGraph() {
      if (emptyEl) emptyEl.style.display = "none";
      wrapEl.style.display = "";
      view.resize();
    }

    function updateButtons(meta) {
      const running = String(meta?.state || "") === "running";
      if (btnBuild) btnBuild.disabled = running || busy;
      if (btnBuildBig) btnBuildBig.disabled = running || busy;
      if (btnRefresh) btnRefresh.disabled = busy;
      const hasGraph = !!meta?.papers_count;
      if (btnBuild) btnBuild.textContent = hasGraph ? "重新分析" : "开始 AI 分析";
    }

    async function fetchState() {
      return await fetchJSON("/api/relationship");
    }

    async function loadAndRender() {
      const data = await fetchState();
      const meta = data.meta || {};
      const graph = data.graph || {};

      updateButtons(meta);

      const state = String(meta.state || "idle");
      if (state === "running") {
        setStatus("AI 分析中…请稍候（可在本页等待完成）");
        showEmpty();
        return { meta, graph };
      }
      if (state === "failed") {
        setStatus(`分析失败：${meta.error || "unknown"}`);
        showEmpty();
        return { meta, graph };
      }

      const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
      const edges = Array.isArray(graph.edges) ? graph.edges : [];
      if (!nodes.length) {
        setStatus("尚未生成图谱。点击“开始 AI 分析”。");
        showEmpty();
        return { meta, graph };
      }

      const ts = meta.updated_at ? ` · ${meta.updated_at}` : "";
      setStatus(`已生成：${nodes.length} 篇 · ${edges.length} 条关系${ts}`);
      showGraph();
      view.setGraph(graph);
      return { meta, graph };
    }

    async function pollUntilDone(timeoutMs = 10 * 60 * 1000) {
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        const data = await fetchState();
        const meta = data.meta || {};
        updateButtons(meta);
        if (String(meta.state || "") !== "running") return data;
        setStatus("AI 分析中…请稍候（大约 10-60 秒）");
        await new Promise((r) => setTimeout(r, 1200));
      }
      throw new Error("分析超时，请稍后点击刷新查看结果");
    }

    async function startBuild(force = false) {
      if (busy) return;
      busy = true;
      updateButtons({});
      setStatus("已提交分析任务…");
      try {
        const maxPapers = Number(maxEl?.value || 30) || 30;
        await fetchJSON("/api/relationship/build", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ max_papers: maxPapers, force: !!force }),
        });
        await pollUntilDone();
        await loadAndRender();
      } catch (e) {
        alert(`请求失败：${e.message || e}`);
        await loadAndRender().catch(() => { });
      } finally {
        busy = false;
        updateButtons({});
      }
    }

    btnBuild?.addEventListener("click", () => startBuild(true));
    btnBuildBig?.addEventListener("click", () => startBuild(true));
    btnRefresh?.addEventListener("click", () => loadAndRender().catch((e) => alert(e.message || e)));

    await loadAndRender().catch((e) => setStatus(`加载失败：${e.message || e}`));
    // If the graph is running (triggered elsewhere), keep polling.
    const initial = await fetchState().catch(() => null);
    if (initial?.meta?.state === "running") {
      pollUntilDone().then(loadAndRender).catch(() => { });
    }
  }

  function initAiChat() {
    const fab = $("#ai-fab");
    const modal = $("#ai-chat");
    const btnClose = $("#ai-chat-close");
    const btnClear = $("#ai-chat-clear");
    const modelEl = $("#ai-chat-model");
    const toggleSnippets = $("#ai-chat-snippets");
    const messagesEl = $("#ai-chat-messages");
    const inputEl = $("#ai-chat-input");
    const btnSend = $("#ai-chat-send");

    if (!fab || !modal || !messagesEl || !inputEl || !btnSend) return;

    const jobId = String(document.body.dataset.jobId || "").trim();
    if (!jobId) {
      fab.style.display = "none";
      return;
    }

    const models = ["nano-banana-fast", "nano-banana", "gemini-3-pro", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"];
    const storageKeyModel = "ai_chat_model";
    const storageKeySnippets = "ai_chat_snippets";

    function loadPref(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v == null ? fallback : v;
      } catch {
        return fallback;
      }
    }

    function savePref(key, value) {
      try {
        localStorage.setItem(key, String(value));
      } catch { }
    }

    function ensureModels() {
      if (!modelEl) return;
      modelEl.innerHTML = models.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
      const saved = String(loadPref(storageKeyModel, "gemini-2.5-flash") || "").trim();
      modelEl.value = models.includes(saved) ? saved : "gemini-2.5-flash";
      modelEl.addEventListener("change", () => savePref(storageKeyModel, modelEl.value || ""));
    }

    if (toggleSnippets) {
      const saved = loadPref(storageKeySnippets, "0");
      toggleSnippets.checked = saved === "1" || saved === "true";
      toggleSnippets.addEventListener("change", () => savePref(storageKeySnippets, toggleSnippets.checked ? "1" : "0"));
    }

    ensureModels();

    let open = false;
    let busy = false;
    let aborter = null;
    const chat = [];

    function render() {
      if (!messagesEl) return;
      if (!chat.length) {
        messagesEl.innerHTML = `<div class="hint">你可以询问该论文：主要贡献、方法、实验设置、结论、局限、如何复现等。</div>`;
        return;
      }
      messagesEl.innerHTML = chat
        .map((m) => `<div class="ai-msg ${escapeHtml(m.role)}">${escapeHtml(m.content || "")}</div>`)
        .join("");
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setOpen(value) {
      open = !!value;
      if (open) {
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        render();
        setTimeout(() => inputEl?.focus(), 0);
      } else {
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
      }
    }

    async function streamCompletion({ model, messages, context, signal, onDelta }) {
      const resp = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, stream: true, messages, context }),
        signal,
      });

      if (!resp.ok) {
        const t = await resp.text().catch(() => "");
        throw new Error(t || `HTTP ${resp.status}`);
      }

      const ctype = String(resp.headers.get("Content-Type") || "");
      if (ctype.includes("application/json")) {
        const data = await resp.json();
        const choice = data?.choices?.[0] || {};
        const content = choice?.message?.content ?? choice?.delta?.content ?? choice?.text ?? "";
        if (content) onDelta(String(content));
        return;
      }

      if (!resp.body) throw new Error("Empty response body");
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        buf = buf.replace(/\r/g, "");

        let idx = 0;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const event = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          for (const line of event.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const dataStr = line.slice(5).trim();
            if (!dataStr) continue;
            if (dataStr === "[DONE]") return;
            let obj = null;
            try {
              obj = JSON.parse(dataStr);
            } catch {
              continue;
            }
            const choice = obj?.choices?.[0];
            const delta = choice?.delta?.content ?? "";
            const full = choice?.message?.content ?? "";
            const text = delta || full;
            if (text) onDelta(String(text));
          }
        }
      }
    }

    async function send() {
      const text = String(inputEl?.value || "").trim();
      if (!text) return;
      if (busy) return;

      chat.push({ role: "user", content: text });
      inputEl.value = "";

      const assistant = { role: "assistant", content: "" };
      chat.push(assistant);
      render();

      const assistantEl = messagesEl?.lastElementChild;

      const context = toggleSnippets?.checked ? "lite+snippets" : "lite";
      const model = String(modelEl?.value || "gemini-2.5-flash").trim() || "gemini-2.5-flash";

      const history = chat
        .filter((m) => m && (m.role === "user" || m.role === "assistant"))
        .slice(-12)
        .map((m) => ({ role: m.role, content: String(m.content || "") }));

      busy = true;
      btnSend.disabled = true;
      inputEl.disabled = true;
      aborter = new AbortController();

      try {
        await streamCompletion({
          model,
          messages: history,
          context,
          signal: aborter.signal,
          onDelta: (delta) => {
            assistant.content += delta;
            if (assistantEl) assistantEl.textContent = assistant.content;
            if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
          },
        });
      } catch (e) {
        assistant.content = `（请求失败：${e.message || e}）`;
        render();
      } finally {
        busy = false;
        btnSend.disabled = false;
        inputEl.disabled = false;
        aborter = null;
        inputEl.focus();
      }
    }

    fab.style.display = "";
    fab.addEventListener("click", () => setOpen(true));
    btnClose?.addEventListener("click", () => setOpen(false));
    btnClear?.addEventListener("click", () => {
      if (busy) return;
      chat.length = 0;
      render();
      inputEl.focus();
    });
    btnSend.addEventListener("click", send);

    inputEl.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (e.shiftKey) return;
      e.preventDefault();
      send();
    });

    modal.addEventListener("click", (e) => {
      if (e.target === modal) setOpen(false);
    });

    document.addEventListener("keydown", (e) => {
      if (!open) return;
      if (e.key === "Escape") setOpen(false);
    });
  }

  const page = document.body.dataset.page;
  initUserBar().catch(() => { });
  initAiChat();
  if (page === "home") initHome();
  if (page === "job") initJob();
  if (page === "weekly") initWeekly();
  if (page === "tags") initTags();
  if (page === "draw") initDraw();
  if (page === "translate") initTranslate();
  if (page === "relationship") initRelationship();
})();
