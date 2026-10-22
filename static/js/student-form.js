(() => {
  "use strict";
  const status = document.getElementById("id_status");
  const date = document.getElementById("id_resignation_date");
  if (!status || !date) return;
  const update = () => {
    date.required = status.value === "resigned";
    date.closest("p").hidden = !date.required;
  };
  status.addEventListener("change", () => {
    if (status.value === "studying") date.value = "";
    update();
  });
  update();
})();
