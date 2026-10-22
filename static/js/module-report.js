(() => {
  "use strict";
  document.querySelectorAll(".report-module").forEach(panel => {
    const categories = JSON.parse(panel.querySelector('script[type="application/json"]').textContent);
    panel.querySelectorAll('select[name$="_category"]').forEach(select => {
      select.addEventListener("change", () => {
        const category = categories.find(item => String(item.id) === select.value);
        const objective = panel.querySelector(`[name="${select.name.replace(/_category$/, "_objective")}"]`);
        objective.value = category ? category.objective : "";
      });
    });
  });
})();
