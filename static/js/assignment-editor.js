(() => {
  "use strict";
  const container = document.getElementById("scheme-categories");
  if (!container) return;
  const locked = container.dataset.locked === "true";
  const mode = document.getElementById("id_calculation_mode");
  const hidden = document.getElementById("id_scheme_json");
  const error = document.getElementById("scheme-editor-error");
  const numberValue = value => value == null || value === "" ? "" : String(Number(value));
  const stringValue = value => typeof value === "string" || typeof value === "number" ? String(value) : "";
  const presets = JSON.parse(document.getElementById("scheme-presets").textContent);
  const status = document.getElementById("scheme-preset-status");
  const restoreButton = document.getElementById("restore-scheme");
  let previousScheme = null;
  const library = JSON.parse(document.getElementById("marking-library").textContent);
  const matchesName = (item, name) => [item.name, item.name_th, item.name_en].filter(Boolean).some(value => value === name);
  function fillSubcategorySelect(category, row) {
    const select = row.querySelector(".library-subcategory");
    const current = row.querySelector('[data-field="name"]').value;
    select.replaceChildren(new Option(gettext("Custom name / optional"), ""));
    const selected = category.querySelector(".library-category").value;
    for (const group of library.filter(item => !selected || String(item.id) === selected)) {
      const options = document.createElement("optgroup");
      options.label = group.name;
      group.items.forEach((item, index) => {
        const option = new Option(item.name, `${group.id}:${index}`);
        options.append(option);
        if (matchesName(item, current)) option.selected = true;
      });
      if (options.children.length) select.append(options);
    }
    select.hidden = locked;
  }
  function setupCategorySelect(category, data) {
    const select = category.querySelector(".library-category");
    select.append(new Option(gettext("Custom name / optional"), ""));
    library.forEach(item => select.append(new Option(item.name, item.id)));
    select.value = String(library.find(item => matchesName(item, data.name))?.id || "");
    category.querySelector(".library-category-control").hidden = locked;
    select.addEventListener("change", () => {
      const selected = library.find(item => String(item.id) === select.value);
      if (selected) category.querySelector('[data-field="name"]').value = selected.name;
      category.querySelectorAll(".scheme-items tr").forEach(row => fillSubcategorySelect(category, row));
    });
  }
  function addItem(category, data = {}) {
    const row = document.getElementById("item-template").content.firstElementChild.cloneNode(true);
    row.dataset.id = data.id ?? "";
    ["name", "maximum"].forEach(key => { row.querySelector(`[data-field="${key}"]`).value = key === "name" ? stringValue(data[key]) : numberValue(data[key]); });
    row.querySelector('[data-field="weight"]').value = numberValue(data.weight ?? 1);
    fillSubcategorySelect(category, row);
    row.querySelector(".library-subcategory").addEventListener("change", event => {
      const [groupId, index] = event.target.value.split(":");
      const item = library.find(group => String(group.id) === groupId)?.items[Number(index)];
      if (!item) return;
      row.querySelector('[data-field="name"]').value = item.name;
      if (item.maximum !== "") row.querySelector('[data-field="maximum"]').value = item.maximum;
      row.querySelector('[data-field="weight"]').value = item.weight;
      updateSubcategoryWeights(category);
    });
    row.querySelector('[data-field="name"]').addEventListener("input", () => { row.querySelector(".library-subcategory").value = ""; });
    if (locked) {
      ["name", "maximum"].forEach(key => { row.querySelector(`[data-field="${key}"]`).disabled = true; });
      row.querySelector(".remove-item").hidden = true;
    }
    row.querySelector(".remove-item").addEventListener("click", () => row.remove());
    category.querySelector(".scheme-items").append(row);
    updateSubcategoryWeights(category);
  }
  function addCategory(data = {}) {
    if (!data || typeof data !== "object") data = {};
    const category = document.getElementById("category-template").content.firstElementChild.cloneNode(true);
    category.dataset.id = data.id ?? "";
    ["name", "learning_objective", "weight"].forEach(key => { category.querySelector(`[data-field="${key}"]`).value = key === "weight" ? numberValue(data[key] ?? 0) : stringValue(data[key]); });
    category.querySelector(".remove-category").addEventListener("click", () => category.remove());
    category.querySelector('[data-field="aggregation"]').value = data.aggregation || "sum";
    category.querySelector('[data-field="aggregation"]').addEventListener("change", () => updateSubcategoryWeights(category));
    category.querySelector('[data-field="common_maximum"]').value = numberValue(data.items?.[0]?.maximum ?? "10");
    category.querySelector('[data-field="common_maximum"]').disabled = locked;
    category.querySelector('[data-field="common_maximum"]').addEventListener("input", () => updateSubcategoryWeights(category));
    window.CategoryRubric.mount(category, data.evaluation_rubric);
    setupCategorySelect(category, data);
    if (locked) {
      ["name", "weight"].forEach(key => { category.querySelector(`[data-field="${key}"]`).disabled = true; });
      category.querySelector(".remove-category").hidden = true;
      category.querySelector(".add-item").hidden = true;
    }
    category.querySelector(".add-item").addEventListener("click", () => addItem(category));
    const items = Array.isArray(data.items) ? data.items : [];
    items.forEach(item => addItem(category, item && typeof item === "object" ? item : {}));
    container.append(category);
    updateWeights();
    updateSubcategoryWeights(category);
  }
  function updateSubcategoryWeights(category) {
    const aggregation = category.querySelector('[data-field="aggregation"]').value;
    const weighted = aggregation === "weighted_average";
    const average = aggregation !== "sum";
    const common = category.querySelector('[data-field="common_maximum"]');
    category.querySelector(".common-maximum").hidden = !average;
    common.required = average;
    common.disabled = locked || !average;
    category.querySelectorAll('.scheme-items [data-field="maximum"]').forEach(input => {
      input.readOnly = average;
      if (average && !locked) input.value = common.value;
    });
    category.querySelectorAll(".subcategory-weight").forEach(element => { element.hidden = !weighted; });
    category.querySelectorAll('.scheme-items [data-field="weight"]').forEach(input => { input.disabled = !weighted; });
  }
  function updateWeights() {
    const weighted = mode.value === "weighted";
    container.querySelectorAll(".category-weight").forEach(element => { element.hidden = !weighted; });
    document.getElementById("weight-help").hidden = !weighted;
  }
  function readScheme() {
    return [...container.querySelectorAll(".scheme-category")].map(category => ({
      id:category.dataset.id ? Number(category.dataset.id) : null,
      name: category.querySelector('[data-field="name"]').value.trim(),
      learning_objective:category.querySelector('[data-field="learning_objective"]').value.trim(),
      weight: category.querySelector('[data-field="weight"]').value || "0",
      aggregation:category.querySelector('[data-field="aggregation"]').value,
      evaluation_rubric:window.CategoryRubric.read(category),
      items: [...category.querySelectorAll(".scheme-items tr")].map(row => ({
        id:row.dataset.id ? Number(row.dataset.id) : null,
        ...Object.fromEntries(["name", "maximum", "weight"].map(key => [key, row.querySelector(`[data-field="${key}"]`).value.trim() || (key === "weight" ? "1" : "")]))
      }))
    }));
  }
  function showScheme(scheme) {
    container.replaceChildren();
    (scheme.length ? scheme : [{}]).forEach(addCategory);
    hidden.value = JSON.stringify(readScheme());
    error.textContent = "";
    updateWeights();
  }
  function rememberScheme() {
    previousScheme = {scheme:readScheme(), mode:mode.value};
    restoreButton.hidden = false;
    restoreButton.disabled = false;
  }
  document.getElementById("load-scheme-preset")?.addEventListener("click", () => {
    const preset = presets.find(item => item.id === document.getElementById("scheme-preset").value);
    if (!preset) return;
    rememberScheme();
    mode.value = preset.mode;
    showScheme(preset.scheme);
    status.textContent = interpolate(gettext("%(preset)s loaded. Review the categories, then save the module."), {"preset": preset.name}, true);
  });
  document.getElementById("blank-scheme")?.addEventListener("click", () => {
    rememberScheme();
    showScheme([]);
    status.textContent = gettext("Blank scheme started. Add your own categories, or restore the previous scheme.");
  });
  restoreButton?.addEventListener("click", () => {
    if (!previousScheme) return;
    mode.value = previousScheme.mode;
    showScheme(previousScheme.scheme);
    previousScheme = null;
    restoreButton.hidden = true;
    restoreButton.disabled = true;
    status.textContent = gettext("Previous scheme restored.");
  });
  document.getElementById("add-category")?.addEventListener("click", () => addCategory());
  mode.addEventListener("change", updateWeights);
  const initial = JSON.parse(document.getElementById("initial-scheme").textContent);
  showScheme(initial);
  document.getElementById("assignment-editor").addEventListener("invalid", event => {
    const details = event.target.closest("details");
    if (details) details.open = true;
  }, true);
  document.getElementById("assignment-editor").addEventListener("submit", event => {
    const categories = readScheme();
    if (!categories.length) {
      event.preventDefault();
      error.textContent = gettext("Add at least one marking category.");
      return;
    }
    hidden.value = JSON.stringify(categories);
  });
})();
