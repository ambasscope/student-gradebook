(() => {
  "use strict";
  const form = document.getElementById("marking-library-editor");
  if (!form) return;
  const body = document.getElementById("library-items");
  function add(item = {}) {
    if (body.children.length >= 100) return;
    const row = document.getElementById("library-item-template").content.firstElementChild.cloneNode(true);
    for (const key of ["name_th", "name_en", "maximum", "weight"]) {
      let value = item[key] ?? (key === "weight" ? 1 : "");
      if ((key === "maximum" || key === "weight") && value !== "") value = String(Number(value));
      row.querySelector(`[data-field="${key}"]`).value = typeof value === "string" ? value : "";
    }
    row.querySelector(".remove-item").addEventListener("click", () => row.remove());
    body.append(row);
  }
  JSON.parse(document.getElementById("library-initial-items").textContent).forEach(item => add(item && typeof item === "object" ? item : {}));
  document.getElementById("library-add-item").addEventListener("click", () => add());
  form.addEventListener("submit", () => {
    document.getElementById("id_subcategories_json").value = JSON.stringify([...body.children].map(row =>
      Object.fromEntries(["name_th", "name_en", "maximum", "weight"].map(key => [key, row.querySelector(`[data-field="${key}"]`).value.trim()]))));
  });
})();
