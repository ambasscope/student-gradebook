/* A separate rubric editor for every marking category. */
(() => {
  "use strict";
  const defaults = JSON.parse(document.getElementById("default-evaluation").textContent);
  const presets = JSON.parse(document.getElementById("rubric-presets").textContent);
  const editors = new Set();
  const signature = levels => JSON.stringify(levels.map(band => ({minimum:Number(band.minimum), label:String(band.label).trim(), is_fail:band.is_fail === true})).sort((a, b) => b.minimum - a.minimum));
  function fillSelect(host) {
    const select = host.querySelector(".rubric-preset-select");
    const current = signature(window.CategoryRubric.read(host));
    select.replaceChildren(new Option(gettext("Custom levels"), ""));
    for (const builtin of [true, false]) {
      const group = document.createElement("optgroup");
      group.label = builtin ? gettext("Built-in presets") : gettext("My presets");
      presets.filter(item => item.builtin === builtin).forEach(preset => group.append(new Option(preset.name, preset.id)));
      if (group.children.length) select.append(group);
    }
    select.value = presets.find(preset => signature(preset.levels) === current)?.id || "";
    host.querySelector(".load-rubric-preset").disabled = !select.value;
  }
  window.CategoryRubric = {
    mount(host, levels) {
      const body = host.querySelector(".evaluation-levels");
      const select = host.querySelector(".rubric-preset-select");
      const restore = host.querySelector(".restore-rubric");
      const status = host.querySelector(".rubric-preset-status");
      let previous = null;
      function announce(message, error = false) {
        status.textContent = message;
        status.classList.toggle("errorlist", error);
      }
      function edited() {
        select.value = presets.find(preset => signature(preset.levels) === signature(window.CategoryRubric.read(host)))?.id || "";
        host.querySelector(".load-rubric-preset").disabled = !select.value;
      }
      const add = (level = {}) => {
        if (body.children.length >= 20) return;
        const row = document.getElementById("evaluation-level-template").content.firstElementChild.cloneNode(true);
        row.querySelector('[data-evaluation-field="minimum"]').value = level.minimum == null || level.minimum === "" ? "" : String(Number(level.minimum));
        row.querySelector('[data-evaluation-field="label"]').value = level.label ?? "";
        row.querySelector('[data-evaluation-field="is_fail"]').checked = level.is_fail === true;
        row.querySelector(".remove-evaluation-level").addEventListener("click", () => { row.remove(); edited(); });
        body.append(row);
      };
      const show = rows => { body.replaceChildren(); rows.forEach(add); };
      const remember = () => { previous = window.CategoryRubric.read(host); restore.hidden = false; };
      host.querySelector(".add-evaluation-level").addEventListener("click", () => { add(); edited(); });
      host.querySelector(".reset-evaluation").addEventListener("click", () => {
        remember(); show(defaults); edited(); announce(gettext("Default evaluation loaded. Review the levels before saving."));
      });
      select.addEventListener("change", () => { host.querySelector(".load-rubric-preset").disabled = !select.value; });
      host.querySelector(".load-rubric-preset").addEventListener("click", () => {
        const preset = presets.find(item => item.id === select.value);
        if (!preset) return;
        remember(); show(preset.levels); edited();
        announce(interpolate(gettext("%(preset)s loaded into this editor. Review the levels before saving."), {preset:preset.name}, true));
      });
      restore.addEventListener("click", () => {
        if (!previous) return;
        show(previous); previous = null; restore.hidden = true; edited();
        announce(gettext("Previous rubric restored."));
      });
      body.addEventListener("input", edited);
      const save = host.querySelector(".save-rubric-preset");
      save?.addEventListener("click", async () => {
        const name = host.querySelector(".rubric-preset-name").value.trim();
        if (!name) { announce(gettext("Enter a name for this preset."), true); return; }
        const requested = window.CategoryRubric.read(host);
        save.disabled = true;
        announce(gettext("Saving rubric preset…"));
        try {
          const response = await fetch(host.querySelector(".save-rubric-controls").dataset.saveUrl, {
            method:"POST", credentials:"same-origin",
            headers:{"Content-Type":"application/json", "X-CSRFToken":document.querySelector('[name="csrfmiddlewaretoken"]').value},
            body:JSON.stringify({name, levels:requested})
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || gettext("Could not save this rubric preset. Try again."));
          presets.push(result.preset);
          for (const editor of editors) {
            if (editor.isConnected || editor === host) fillSelect(editor);
            else editors.delete(editor);
          }
          announce(gettext("Rubric preset saved for reuse. Save the module separately to apply your category changes."));
        } catch (error) {
          announce(error instanceof SyntaxError || error instanceof TypeError ? gettext("Could not save this rubric preset. Try again.") : error.message, true);
        } finally { save.disabled = false; }
      });
      show(Array.isArray(levels) ? levels : defaults);
      editors.add(host);
      fillSelect(host);
    },
    read(host) {
      return [...host.querySelectorAll(".evaluation-levels tr")].map(row => ({
        minimum:row.querySelector('[data-evaluation-field="minimum"]').value,
        label:row.querySelector('[data-evaluation-field="label"]').value.trim(),
        is_fail:row.querySelector('[data-evaluation-field="is_fail"]').checked
      }));
    }
  };
})();
