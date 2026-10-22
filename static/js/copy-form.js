(() => {
  "use strict";
  const existing = document.getElementById("id_existing_period");
  if (!existing) return;
  function update() {
    for (const field of ["destination_course", "academic_year", "semester", "classrooms"]) {
      const host = document.querySelector(`[data-copy-field="${field}"]`);
      host.hidden = Boolean(existing.value);
      host.querySelectorAll("input, select").forEach(input => { input.disabled = Boolean(existing.value); });
    }
  }
  existing.addEventListener("change", update);
  update();
})();
