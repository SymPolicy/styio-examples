(function () {
  const gallery = document.getElementById("gallery");
  if (gallery) {
    const search = document.getElementById("q");
    const themeRow = document.getElementById("theme-filters");
    const kindRow = document.getElementById("kind-filters");
    const meta = document.getElementById("result-meta");
    const empty = document.getElementById("empty");
    const cards = Array.from(gallery.querySelectorAll(".card"));
    let theme = "all";
    let kind = "all";

    function setActive(row, attr, value) {
      if (!row) return;
      row.querySelectorAll(".chip").forEach((chip) => {
        chip.classList.toggle("is-active", chip.getAttribute(attr) === value);
      });
    }

    function apply() {
      const query = (search && search.value || "").trim().toLowerCase();
      let shown = 0;
      cards.forEach((card) => {
        const hay = card.getAttribute("data-search") || "";
        const matchTheme = theme === "all" || card.getAttribute("data-theme") === theme;
        const matchKind = kind === "all" || card.getAttribute("data-kind") === kind;
        const matchQuery = !query || hay.indexOf(query) !== -1;
        const visible = matchTheme && matchKind && matchQuery;
        card.hidden = !visible;
        if (visible) shown += 1;
      });
      if (empty) empty.hidden = shown !== 0;
      if (meta) {
        meta.textContent = shown === cards.length
          ? ""
          : shown + " of " + cards.length + " cases";
      }
    }

    if (themeRow) {
      themeRow.addEventListener("click", (event) => {
        const button = event.target.closest("[data-theme]");
        if (!button) return;
        theme = button.getAttribute("data-theme") || "all";
        setActive(themeRow, "data-theme", theme);
        apply();
      });
    }
    if (kindRow) {
      kindRow.addEventListener("click", (event) => {
        const button = event.target.closest("[data-kind]");
        if (!button) return;
        kind = button.getAttribute("data-kind") || "all";
        setActive(kindRow, "data-kind", kind);
        apply();
      });
    }
    if (search) search.addEventListener("input", apply);
  }

  document.querySelectorAll(".tabs").forEach((tablist) => {
    tablist.addEventListener("click", (event) => {
      const button = event.target.closest("[data-tab]");
      if (!button) return;
      const selected = button.getAttribute("data-tab");
      const root = tablist.parentElement;
      tablist.querySelectorAll(".tab").forEach((tab) => {
        tab.classList.toggle("is-active", tab === button);
      });
      root.querySelectorAll(".source-panel").forEach((panel) => {
        const active = panel.id === selected;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
    });
  });
})();
