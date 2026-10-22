(() => {
  "use strict";
  const hidden = document.getElementById("id_objectives_json");
  const fields = [...document.querySelectorAll("[data-objective-category]")];
  if (!hidden || !fields.length) return;
  try {
    const initial = JSON.parse(hidden.value || "{}");
    fields.forEach(field => {
      const value = initial[field.dataset.objectiveCategory];
      if (typeof value === "string") field.value = value;
    });
  } catch { /* Keep the saved objectives visible if a submitted payload was malformed. */ }
  const sync = () => { hidden.value = JSON.stringify(Object.fromEntries(fields.map(field => [field.dataset.objectiveCategory, field.value]))); };
  fields.forEach(field => field.addEventListener("input", sync));
  document.getElementById("assignment-editor").addEventListener("submit", sync);
  sync();
})();
