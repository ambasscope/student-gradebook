# Reusable rubric presets

Open **Modules → Edit module → Category evaluation rubric**. Each category has
its own **Rubric preset** selector. Choose a preset and click **Load preset**,
review or edit its levels, and use **Save module**. Loading or resetting a rubric
keeps a one-step **Restore previous rubric** option until the editor is reloaded.
This also works after marking starts and retains the existing raw scores.

The supplied presets are:

| Preset | Minimum percentages and labels |
| --- | --- |
| Default four levels | 80 Excellent; 60 Good; 50 Pass; 0 Fail |
| Thai four levels | 80 ดีเยี่ยม; 60 ดี; 50 ผ่าน; 0 ไม่ผ่าน |
| Thai three levels | 80 ดี; 50 ผ่าน; 0 ไม่ผ่าน |
| Pass / Fail at 50% | 50 ผ่าน; 0 ไม่ผ่าน |
| Pass / Fail at 60% | 60 ผ่าน; 0 ไม่ผ่าน |

Only each preset's lowest band is flagged **Count as failed**. Flags and labels
can be customized in the editor. All minima are percentages of that category's
maximum, independent of whether its scores use Sum, Average, or Weighted average.

To reuse your own levels, enter a **Preset name** below the category's level
table and click **Save as preset**. This immediately saves a reusable copy in
the local database. It does not save the module form: use **Save module** for
that. The new preset becomes available in all category selectors on that page.
Names must be nonblank, at most 120 characters, and unique among saved presets.

Open **Modules → Rubric presets** to add a preset directly, create an editable
copy of a supplied preset, or edit/rename/delete your saved presets. Built-in
presets stay available and cannot be deleted through the interface. Open editor
pages show the catalog as it was when loaded; refresh to see changes made in
another window. Save any module edits before refreshing.

Applying a preset copies its levels and failure flags into the category. There
is no live link. Editing or deleting a saved preset does not change existing
categories, marks, or assessments. To apply a revised preset to an existing
category, load it there and save the module again. Existing scoring pages must
reload after a category rubric changes, as before. Word and Excel exports use
the category's saved levels, not the preset library.

Saved presets live in the same SQLite database as the rest of the user's data.
They move with a full data backup and are excluded from a clean distribution.
Their rubric labels stay exactly as saved when the interface language changes.

## Choosing your default

Open **Modules → Rubric presets**, choose **Default evaluation rubric**, and
click **Save default rubric**. You can choose any supplied or saved preset.
The choice is stored in the local database and survives closing the app.

New modules and newly added categories start with that rubric. Existing
categories keep their saved levels; copying a module keeps the source module's
rubrics. **Load default** in a category editor loads the currently selected
default and still requires saving the module to apply it.

Editing a preset chosen as default affects future drafts only. Deleting that
preset restores the starter 80 / 60 / 50 rubric for future categories; the
delete confirmation explains this. The default preference moves with the
database when backing up or transferring the data folder.

## Adding a built-in preset in source

Edit `apps/assessments/services/rubric_presets.py` in the active project. Add an
entry to `BUILTIN_PRESETS` with a unique `builtin:` ID, a name, and a levels list.
Each level contains `minimum`, `label`, and an explicit Boolean `is_fail`. Keep
1–20 distinct minima and labels, include a 0% minimum, and use minima from 0 to
100 with at most two decimal places. `bands()` is a helper for presets where
only the lowest level counts as failed; other structures can use explicit lists.
Restart the app after editing. Backups under `app-data/backups/` are historical
copies and are not used as live application source.
