(() => {
  "use strict";
  const offering = document.getElementById("id_offering");
  const unit = document.getElementById("id_unit");
  if (!offering || !unit) return;
  const units = JSON.parse(document.getElementById("module-unit-options").textContent);
  const courses = JSON.parse(document.getElementById("offering-courses").textContent);
  function updateUnits() {
    const selected = unit.value;
    unit.replaceChildren(new Option(gettext("Choose a unit"), ""));
    const available = units.filter(item => item.course === courses[offering.value]);
    available.forEach(item => unit.append(new Option(item.label, String(item.id))));
    unit.value = available.some(item => String(item.id) === selected) ? selected : "";
    document.getElementById("module-unit-help").hidden = available.length > 0;
  }
  offering.addEventListener("change", updateUnits);
  updateUnits();
})();
