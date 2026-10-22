# Marking scheme library

Open **Marking schemes** in the navigation, or use **Modules → Marking schemes**.
Each category has optional Thai and English names, with at least one language
required. Add or remove subcategory rows on its edit page. Each subcategory also
needs at least one name. Its maximum mark is an optional default; its relative
weight must be positive. Delete a category through its confirmation page to
remove it and its subcategories from future choices.

On first setup or upgrade, the app seeds four categories and 15 subcategories
from `apps/assessments/data/marking-scheme_kpac.json`. The file intentionally does
not prescribe maximum marks. Once seeded, the database is authoritative. Deleted
entries are not recreated at startup, and changing the JSON does not overwrite
the user's library.

New modules start with the library categories, without selected subcategories.
Within each category, click **Add subcategory**, then optionally select a library
entry or type a custom name. A selected suggestion copies its name and relative
weight, plus its maximum mark if one was saved. In average modes, the module's
common maximum mark takes precedence. Selecting another category changes the
suggestions and category name while keeping the existing subcategory rows for
review. To reload choices after editing the library in another tab, save the
module and reopen its editor.

Names are copied using the current interface language, falling back to the
other supplied name. Switching the interface language later does not rename
saved module content. The library is a list of reusable suggestions; each module
retains its own objectives, aggregation settings, marking criteria, and rubrics.
Library changes and deletions never alter saved modules or student marks.
After marking starts, category and subcategory names and maxima stay locked.

Both library edits and deletions check a revision to reject stale changes from
another window. The entire library category, including its child rows, saves
atomically. Maximum marks and relative weights use the same decimal validation
as module schemes.
