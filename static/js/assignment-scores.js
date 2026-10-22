(() => {
  "use strict";
  const host = document.getElementById("score-grid");
  if (!host) return;
  const config = JSON.parse(document.getElementById("score-grid-data").textContent);
  const status = document.getElementById("score-status");
  const saveButton = document.getElementById("save-scores");
  const undoButton = document.getElementById("undo-score");
  const redoButton = document.getElementById("redo-score");
  const notesHost = document.getElementById("classroom-notes");
  const secondSaveButton = document.getElementById("save-classroom-record");
  const completionHost = document.getElementById("module-completion");
  const completionError = document.getElementById("module-completion-error");
  const suggestionDetailKeys = [...notesHost.querySelectorAll("[data-suggestion-detail]")].map(input => input.dataset.suggestionDetail);
  let notesBaseline = {...config.classroom_notes};
  const criteria = config.categories.flatMap(category => category.items);
  const byField = new Map(criteria.map(item => [`c_${item.id}`, item]));
  const baseline = new Map(config.rows.map(row => [row.enrollment_id, {...row}]));
  let table, saving = false, dirtyCount = 0, refreshQueued = false, refreshing = false;

  function readNotes() {
    const problemChoices = [...notesHost.querySelectorAll('[name="problem_choices"]:checked')].map(input => input.value);
    const suggestionChoices = [...notesHost.querySelectorAll('[name="suggestion_choices"]:checked')].map(input => input.value);
    return {
      learning_date: document.getElementById("learning-date").value,
      problem:problemChoices.includes("other") ? document.getElementById("classroom-problem").value : "",
      suggestion:suggestionChoices.includes("none") ? "" : document.getElementById("classroom-suggestion").value,
      problem_choices:problemChoices,
      suggestion_choices:suggestionChoices,
      suggestion_details:Object.fromEntries([...notesHost.querySelectorAll("[data-suggestion-detail]")].map(input => [input.dataset.suggestionDetail, suggestionChoices.includes(input.dataset.suggestionDetail) ? input.value : ""])),
      revision:notesBaseline.revision,
      module_status:completionHost.querySelector('[name="module_status"]:checked')?.value || ""
    };
  }
  // Normalize textarea newlines and checkbox ordering to the displayed values.
  notesBaseline = readNotes();
  function notesSnapshot(notes) {
    return JSON.stringify([
      notes.learning_date || "",
      notes.module_status,
      notes.problem,
      notes.suggestion,
      notes.problem_choices,
      notes.suggestion_choices,
      suggestionDetailKeys.map(key => notes.suggestion_details[key])
    ]);
}
  function notesChanged() { return notesSnapshot(readNotes()) !== notesSnapshot(notesBaseline); }
  function saveControls(disabled) {
    notesHost.querySelectorAll("input,textarea").forEach(input => { input.disabled = disabled; });
    host.querySelectorAll(".attendance-checkbox").forEach(input => { input.disabled = disabled; });
    completionHost.querySelectorAll("input").forEach(input => { input.disabled = disabled; });
    if (!disabled) updateCommentFields();
  }
  function updateCommentFields() {
    const notes = readNotes();
    document.getElementById("classroom-problem").disabled = saving || !notes.problem_choices.includes("other");
    document.getElementById("classroom-suggestion").disabled = saving || notes.suggestion_choices.includes("none");
    notesHost.querySelectorAll("[data-suggestion-detail]").forEach(input => { input.disabled = saving || !notes.suggestion_choices.includes(input.dataset.suggestionDetail); });
  }
  updateCommentFields();

  function canonical(value, maximum) {
    if (value === null || value === undefined || value === "" || typeof value === "string" && !value.trim()) return {value:null};
    if (typeof value !== "string" && typeof value !== "number") return {error:gettext("Enter a number.")};
    const text = String(value).trim();
    if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return {error:gettext("Enter a nonnegative number.")};
    const number = Number(text);
    if (!Number.isFinite(number) || number < 0 || number > Number(maximum)) return {error:interpolate(gettext("Maximum mark is %(maximum)s."), {"maximum": maximum}, true)};
    if (Math.abs(number * 100 - Math.round(number * 100)) > 0.000001) return {error:gettext("Use at most two decimal places.")};
    return {value:number.toFixed(2)};
  }
  function announce(message, error = false) {
    status.textContent = message;
    status.classList.toggle("error", error);
  }
  function escapeText(value) {
    const element = document.createElement("span");
    element.textContent = value;
    return element.innerHTML;
  }
  function scoreFormatter(cell) {
    const field = cell.getField(), item = byField.get(field);
    const current = canonical(cell.getValue(), item.maximum);
    const previous = canonical(baseline.get(cell.getRow().getIndex())?.[field], item.maximum);
    const element = cell.getElement();
    element.classList.toggle("score-invalid", Boolean(current.error));
    element.classList.toggle("score-dirty", Boolean(current.error) || current.value !== previous.value);
    element.title = current.error || interpolate(gettext("%(name)s; maximum %(maximum)s"), {"name": item.name, "maximum": item.maximum}, true);
    const content = document.createElement("span");
    content.textContent = current.value === null ? "" : current.error ? String(cell.getValue()) : String(Number(current.value));
    return content;
  }
  function attendanceFormatter(cell) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "attendance-checkbox";
    input.checked = cell.getValue() === true;
    input.disabled = saving;
    input.setAttribute("aria-label", interpolate(gettext("Attendance for %(student)s"), {student:cell.getRow().getData().student_name}, true));
    ["pointerdown", "mousedown", "click"].forEach(event => input.addEventListener(event, event => event.stopPropagation()));
    input.addEventListener("change", () => {
      if (saving) { input.checked = cell.getValue() === true; return; }
      cell.setValue(input.checked);
      scheduleRefresh();
    });
    cell.getElement().classList.toggle("score-dirty", cell.getValue() !== baseline.get(cell.getRow().getIndex()).present);
    return input;
  }
  function subtotal(row, category) {
    let totalUnits = 0n, maximumUnits = 0n, divisor = 0n, marked = 0;
    category.items.forEach(item => {
      const weight = category.aggregation === "weighted_average" ? BigInt(Math.round(Number(item.weight) * 100)) : 1n;
      maximumUnits += BigInt(Math.round(Number(item.maximum) * 100)) * weight;
      divisor += weight;
      const value = canonical(row[`c_${item.id}`], item.maximum);
      if (!value.error && value.value !== null) { totalUnits += BigInt(Math.round(Number(value.value) * 100)) * weight; marked++; }
    });
    if (category.aggregation === "sum") divisor = 1n;
    const rounded = divisor ? (totalUnits * 2n + divisor) / (divisor * 2n) : 0n;
    return {total:divisor ? Number(totalUnits) / Number(divisor) / 100 : 0,
      maximum:divisor ? Number(maximumUnits) / Number(divisor) / 100 : 0,
      display:String(Number(rounded) / 100), totalUnits, maximumUnits, divisor, marked};
  }
  function evaluation(row, category) {
    const result = subtotal(row, category);
    if (!category.items.length || result.marked !== category.items.length || !result.maximumUnits) return gettext("Pending");
    // Integers keep decimal marks exact at the percentage boundaries.
    const level = category.evaluation_rubric.find(band => result.totalUnits * 10000n >= result.maximumUnits * BigInt(Math.round(Number(band.minimum) * 100)));
    return level ? level.label : gettext("Pending");
  }
  function overall(row) {
    let numerator = 0n, denominator = 1n, marked = 0;
    config.categories.forEach(category => {
      const result = subtotal(row, category);
      marked += result.marked;
      const weighted = config.mode === "weighted";
      const nextDenominator = weighted ? result.maximumUnits : result.divisor;
      if (!nextDenominator) return;
      const nextNumerator = weighted ? result.totalUnits * BigInt(Math.round(Number(category.weight) * 100)) : result.totalUnits;
      numerator = numerator * nextDenominator + nextNumerator * denominator;
      denominator *= nextDenominator;
    });
    const rounded = (numerator * 2n + denominator) / (denominator * 2n);
    return {display:String(Number(rounded) / 100), marked};
  }
  function inspect() {
    const changes = [], attendanceChanges = [], invalid = [];
    table.getData().forEach(row => {
      const original = baseline.get(row.enrollment_id);
      if (typeof row.present !== "boolean") invalid.push({row, item:{name:gettext("Attendance")}, error:gettext("Attendance must be checked or unchecked.")});
      else if (row.present !== original.present) attendanceChanges.push({enrollment_id:row.enrollment_id, value:row.present, previous:original.present});
      criteria.forEach(item => {
        const field = `c_${item.id}`;
        const current = canonical(row[field], item.maximum);
        const old = canonical(original?.[field], item.maximum);
        if (current.error) invalid.push({row, item, error:current.error});
        else if (current.value !== old.value) changes.push({enrollment_id:row.enrollment_id, criterion_id:item.id, value:current.value, previous:old.value});
      });
    });
    return {changes, attendanceChanges, invalid, notesChanged:notesChanged()};
  }
  function refresh() {
    refreshQueued = false;
    if (!table) return;
    const {changes, attendanceChanges, invalid, notesChanged} = inspect();
    const cellChanges = changes.length + attendanceChanges.length;
    const pending = cellChanges + Number(notesChanged);
    dirtyCount = pending + invalid.length;
    saveButton.disabled = saving || !pending || Boolean(invalid.length) || cellChanges > 10000;
    secondSaveButton.disabled = saveButton.disabled;
    undoButton.disabled = saving || !table.getHistoryUndoSize();
    redoButton.disabled = saving || !table.getHistoryRedoSize();
    // Keep existing cells alive: row.reformat() deletes cells and their undo history.
    refreshing = true;
    table.getRows().forEach(row => {
      const data = row.getData(), total = overall(data), calculated = {};
      config.categories.forEach(category => {
        const result = subtotal(data, category);
        calculated[`subtotal_${category.id}`] = result.marked ? result.display : "—";
        calculated[`evaluation_${category.id}`] = evaluation(data, category);
      });
      calculated.entered_total = total.marked ? total.display : "—";
      calculated.progress = `${total.marked}/${criteria.length}`;
      if (Object.entries(calculated).some(([key, value]) => data[key] !== value)) row.update(calculated);
      row.getCells().forEach(cell => {
        if (cell.getField() === "present") {
          cell.getElement().classList.toggle("score-dirty", cell.getValue() !== baseline.get(row.getIndex()).present);
          const checkbox = cell.getElement().querySelector(".attendance-checkbox");
          if (checkbox) { checkbox.checked = cell.getValue() === true; checkbox.disabled = saving; }
        }
        if (byField.has(cell.getField()) && !cell.getElement().classList.contains("tabulator-editing")) {
          cell.getElement().replaceChildren(scoreFormatter(cell));
        }
      });
    });
    refreshing = false;
    if (invalid.length) announce(interpolate(gettext("%(count)s invalid score cell(s). %(student_id)s: %(name)s — %(error)s"), {"count": invalid.length, "student_id": invalid[0].row.student_id, "name": invalid[0].item.name, "error": invalid[0].error}, true), true);
    else if (cellChanges > 10000) announce(gettext("Save smaller batches, up to 10,000 cell changes at a time."), true);
    else if (pending) announce(interpolate(gettext("%(count)s unsaved change(s) in scores, attendance, or classroom comments."), {count:pending}, true));
    else announce(config.rows.length ? gettext("Scores, attendance, and classroom comments are saved. Blank scores are unmarked.") : gettext("No enrolled students in this classroom. You can still save classroom comments."));
  }
  function scheduleRefresh() {
    if (refreshing) return;
    if (!refreshQueued) { refreshQueued = true; requestAnimationFrame(refresh); }
  }
  function parseClipboard(text) {
    if (saving) return false;
    if (!config.scheme_ready) { announce(gettext("Finish the marking scheme before entering scores."), true); return false; }
    const rows = String(text).replace(/\r\n?/g, "\n").split("\n");
    while (rows.length && rows[rows.length - 1] === "") rows.pop();
    const data = rows.map(row => row.split("\t"));
    if (!data.length || data.some(row => row.length !== data[0].length) || data.length * data[0].length > 10000) {
      announce(gettext("Paste a rectangular block with at most 10,000 score cells."), true); return false;
    }
    return data;
  }
  function pasteScores(data) {
    if (saving) return [];
    const selected = table.getRanges()[0];
    if (!selected) { announce(gettext("Select a score cell before pasting."), true); return []; }
    const selection = selected.getCells(), first = selection[0]?.[0];
    if (!first || !byField.has(first.getField())) { announce(gettext("Start the paste on a score cell. Student details are read-only."), true); return []; }
    const single = selection.length === 1 && selection[0].length === 1;
    const height = single ? data.length : selection.length;
    const width = single ? data[0].length : selection[0].length;
    const rows = table.getRows("active");
    const start = rows.findIndex(row => row.getIndex() === first.getRow().getIndex());
    const fields = first.getRow().getCells().filter(cell => cell.getField() && cell.getColumn().isVisible()).map(cell => cell.getField());
    const left = fields.indexOf(first.getField());
    const targets = fields.slice(left, left + width);
    if (start < 0 || start + height > rows.length || targets.length !== width || targets.some(field => !byField.has(field))) {
      announce(gettext("The paste extends beyond the students or editable scoring columns. Paste score values only."), true); return [];
    }
    const values = Array.from({length:height}, (_, y) => targets.map((field, x) => data[y % data.length][x % data[0].length]));
    for (const row of values) {
      for (let x = 0; x < row.length; x++) {
        const result = canonical(row[x], byField.get(targets[x]).maximum);
        if (result.error) { announce(interpolate(gettext("Paste rejected: %(name)s — %(error)s"), {"name": byField.get(targets[x]).name, "error": result.error}, true), true); return []; }
      }
    }
    const last = rows[start + height - 1].getCell(targets[width - 1]);
    if (!last) { announce(gettext("The target cells are unavailable. Select a smaller block."), true); return []; }
    // A new range preserves the bounds of earlier undo actions.
    const ready = range => {
      const cell = range.getCells()[0]?.[0];
      if (!cell || cell.getRow().getIndex() !== first.getRow().getIndex() || cell.getField() !== first.getField()) return;
      table.off("rangeAdded", ready);
      range.setData(values);
      scheduleRefresh();
    };
    table.on("rangeAdded", ready);
    table.addRange(first, last);
    return rows.slice(start, start + height);
  }
  const columns = [
    {title:gettext("Roll no."), field:"roll_number", frozen:true, width:85, editor:false, formatter:"plaintext", headerSort:false},
    {title:gettext("Student ID"), field:"student_id", frozen:true, width:115, editor:false, formatter:"plaintext", headerSort:false},
    {title:gettext("Student name"), field:"student_name", frozen:true, width:190, editor:false, formatter:"plaintext", headerSort:false},
    {title:gettext("Attendance"), field:"present", frozen:true, width:105, editor:false, formatter:attendanceFormatter, headerSort:false, hozAlign:"center"},
    ...config.categories.filter(category => category.items.length).map(category => ({
      title:escapeText(`${category.name}${config.mode === "weighted" ? ` (${category.weight}%)` : ""}`),
      columns:category.items.map(item => ({
          title:escapeText(`${item.name} / ${Number(item.maximum)}${category.aggregation === "weighted_average" ? ` (${gettext("Subcategory weight")}: ${item.weight})` : ""}`), field:`c_${item.id}`, width:160,
          editor:"number", editorParams:{min:0, max:Number(item.maximum), step:0.01, selectContents:true},
          editable:() => !saving && config.scheme_ready,
          validator:(cell, value) => !canonical(value, item.maximum).error,
          formatter:scoreFormatter, headerSort:false, hozAlign:"right"
        }))
    })),
    {title:gettext("Summary"), columns:[
      ...config.categories.flatMap(category => [{title:escapeText(`${category.name} · ${category.aggregation_label}`), field:`subtotal_${category.id}`, width:190, editor:false, headerSort:false, hozAlign:"right", formatter:cell => {
          const result = subtotal(cell.getRow().getData(), category);
          return result.marked ? result.display : "—";
        }}, {title:escapeText(interpolate(gettext("%(category)s evaluation"), {"category": category.name}, true)), field:`evaluation_${category.id}`, width:190, editor:false, headerSort:false, cssClass:"score-evaluation", formatter:cell => {
          const text = document.createElement("span");
          text.textContent = evaluation(cell.getRow().getData(), category);
          return text;
        }}]),
    {title:config.mode === "weighted" ? gettext("Total / 100") : gettext("Entered total"), field:"entered_total", width:120, editor:false, headerSort:false, hozAlign:"right", formatter:cell => {
      const result = overall(cell.getRow().getData());
      return result.marked ? result.display : "—";
    }},
    {title:gettext("Marked"), field:"progress", width:95, editor:false, headerSort:false, formatter:cell => `${overall(cell.getRow().getData()).marked}/${criteria.length}`}
    ]}
  ];
  table = new Tabulator(host, {
    data:config.rows, index:"enrollment_id", height:`${Math.min(550, Math.max(220, 100 + config.rows.length * 34))}px`, layout:"fitData",
    columns, history:true, selectableRange:1, selectableRangeColumns:true,
    selectableRangeRows:true, selectableRangeFill:config.scheme_ready,
    selectableRangeClearCells:false, editTriggerEvent:"dblclick",
    validationMode:"blocking", clipboard:true, clipboardCopyStyled:false,
    clipboardCopyRowRange:"range", clipboardCopyConfig:{rowHeaders:false, columnHeaders:false},
    clipboardPasteParser:parseClipboard, clipboardPasteAction:pasteScores,
    rowHeader:{formatter:"rownum", headerSort:false, resizable:false, frozen:true, width:40, editor:false},
    columnDefaults:{resizable:"header"}, placeholder:gettext("No enrolled students in this classroom")
  });
  ["tableBuilt", "cellEdited", "dataChanged", "historyUndo", "historyRedo"].forEach(event => table.on(event, scheduleRefresh));
  table.on("rangeEdited", () => {
    const invalid = inspect().invalid;
    if (invalid.length && table.getHistoryUndoSize()) {
      // Range fill/paste bypasses editor validation in Tabulator; undo bad batches.
      queueMicrotask(() => {
        table.undo(); refresh();
        announce(interpolate(gettext("Fill/paste was rejected: %(name)s — %(error)s"), {"name": invalid[0].item.name, "error": invalid[0].error}, true), true);
      });
    } else scheduleRefresh();
  });
  undoButton.addEventListener("click", () => { table.undo(); scheduleRefresh(); });
  redoButton.addEventListener("click", () => { table.redo(); scheduleRefresh(); });
  const ranges = () => table.getRanges();
  document.getElementById("fill-selection").addEventListener("click", () => {
    if (saving) return;
    if (!config.scheme_ready) { announce(gettext("Finish the marking scheme before entering scores."), true); return; }
    const selected = ranges();
    if (!selected.length) { announce(gettext("Select score cells before filling."), true); return; }
    const value = document.getElementById("fill-value").value;
    if (!value.trim()) { announce(gettext("Enter a fill value. Use Clear selection to make cells unmarked."), true); return; }
    const emptyOnly = document.getElementById("fill-empty").checked;
    for (const range of selected) {
      const cells = range.getCells();
      const targets = cells.flat().filter(cell => byField.has(cell.getField()) && (!emptyOnly || canonical(cell.getValue(), byField.get(cell.getField()).maximum).value === null));
      const invalid = targets.find(cell => canonical(value, byField.get(cell.getField()).maximum).error);
      if (invalid) { announce(interpolate(gettext("Fill rejected: %(error)s"), {"error": canonical(value, byField.get(invalid.getField()).maximum).error}, true), true); return; }
      range.setData(cells.map(row => row.map(cell => byField.has(cell.getField()) && (!emptyOnly || canonical(cell.getValue(), byField.get(cell.getField()).maximum).value === null) ? value : cell.getValue())));
    }
    scheduleRefresh();
  });
  function clearSelection() {
    if (saving) return;
    if (!ranges().length) { announce(gettext("Select score cells to clear."), true); return; }
    ranges().forEach(range => range.setData(range.getCells().map(row => row.map(cell => byField.has(cell.getField()) ? null : cell.getValue()))));
    scheduleRefresh();
  }
  document.getElementById("clear-selection").addEventListener("click", clearSelection);
  host.addEventListener("keydown", event => {
    if ((event.key === "Delete" || event.key === "Backspace") && !event.target.closest("input,textarea")) {
      event.preventDefault(); event.stopPropagation(); clearSelection();
    }
  }, true);
  document.getElementById("score-search").addEventListener("input", event => {
    const query = event.target.value.trim().toLocaleLowerCase();
    table.setFilter(row => row.student_id.toLocaleLowerCase().includes(query) || row.student_name.toLocaleLowerCase().includes(query) || String(row.roll_number ?? "").includes(query));
  });
  notesHost.addEventListener("input", scheduleRefresh);
  completionHost.addEventListener("change", event => {
    if (event.target.checked) completionHost.querySelectorAll('input[name="module_status"]').forEach(input => { if (input !== event.target) input.checked = false; });
    completionError.textContent = "";
    scheduleRefresh();
  });
  notesHost.addEventListener("change", event => {
    const choice = event.target;
    if (choice.name === "suggestion_choices" && choice.checked) {
      if (choice.value === "none") notesHost.querySelectorAll('[name="suggestion_choices"]').forEach(input => { if (input !== choice) input.checked = false; });
      else notesHost.querySelector('[name="suggestion_choices"][value="none"]').checked = false;
    }
    updateCommentFields();
    scheduleRefresh();
  });
  secondSaveButton.addEventListener("click", () => saveButton.click());
  saveButton.addEventListener("click", async () => {
    if (saving) return;
    // Commit an active editor by moving focus to the save button.
    saveButton.focus({preventScroll:true});
    await new Promise(resolve => setTimeout(resolve, 0));
    const {changes, attendanceChanges, invalid, notesChanged} = inspect();
    const cellChanges = changes.length + attendanceChanges.length;
    if (invalid.length || (!cellChanges && !notesChanged) || cellChanges > 10000) { refresh(); return; }
    const notes = notesChanged ? readNotes() : null;
    if (!readNotes().module_status) {
      completionError.textContent = gettext("Choose Module completed or Module uncompleted before saving.");
      completionHost.scrollIntoView({block:"nearest"});
      completionHost.querySelector("input").focus({preventScroll:true});
      return;
    }
    saving = true; saveButton.disabled = true; secondSaveButton.disabled = true; undoButton.disabled = true; redoButton.disabled = true;
    saveControls(true);
    host.style.pointerEvents = "none";
    announce(gettext("Saving scores, attendance, and classroom comments…"));
    try {
      const response = await fetch(config.save_url, {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json", "X-CSRFToken":document.querySelector('#score-csrf [name="csrfmiddlewaretoken"]').value},
        body:JSON.stringify({scheme_revision:config.scheme_revision, roster_signature:config.roster_signature, changes, attendance_changes:attendanceChanges, ...(notes ? {classroom_notes:notes} : {})})
      });
      if (!response.headers.get("content-type")?.includes("application/json")) throw new Error(gettext("The app returned an unexpected response. Reload the page before saving."));
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || gettext("Scores could not be saved."));
      // Only submitted cells become the baseline; retain any independent changes.
      changes.forEach(change => {
        const original = baseline.get(change.enrollment_id);
        original[`c_${change.criterion_id}`] = change.value;
      });
      attendanceChanges.forEach(change => { baseline.get(change.enrollment_id).present = change.value; });
      if (notes) notesBaseline = result.classroom_notes;
      table.clearHistory();
      saving = false; host.style.pointerEvents = ""; saveControls(false); refresh();
      if (result.reload_required) { window.location.reload(); return; }
      announce(interpolate(gettext("Saved %(scores)s score change(s), %(attendance)s attendance change(s), and %(notes)s classroom comment update(s)."), {scores:result.saved, attendance:result.attendance_saved, notes:result.notes_saved}, true));
    } catch (error) {
      saving = false; host.style.pointerEvents = ""; saveControls(false); refresh();
      announce(interpolate(gettext("%(error)s Your unsaved entries remain in this page."), {"error": error.message}, true), true);
    }
  });
  window.addEventListener("beforeunload", event => {
    const pending = table ? inspect() : null;
    if (dirtyCount || saving || notesChanged() || pending && (pending.changes.length || pending.attendanceChanges.length || pending.invalid.length)) { event.preventDefault(); event.returnValue = ""; }
  });
  function preventLosingEdits(event) {
    const pending = inspect();
    if (saving || dirtyCount || host.querySelector(".tabulator-editing") || pending.changes.length || pending.attendanceChanges.length || pending.invalid.length || pending.notesChanged) event.preventDefault();
  }
  window.addEventListener("gradebook:before-language-change", preventLosingEdits);
  window.addEventListener("gradebook:before-close", preventLosingEdits);
})();
