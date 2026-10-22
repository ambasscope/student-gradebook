(() => {
  "use strict";
  const form = document.getElementById("rubric-preset-editor");
  if (!form) return;
  const host = document.getElementById("rubric-preset-levels");
  window.CategoryRubric.mount(host, JSON.parse(document.getElementById("initial-rubric").textContent));
  form.addEventListener("submit", () => {
    document.getElementById("id_rubric_json").value = JSON.stringify(window.CategoryRubric.read(host));
  });
})();
