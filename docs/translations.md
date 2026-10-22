# English and Thai interface

Use the English / ไทย toggle in the application header to switch immediately.
The selection is stored in a browser cookie, with no account or database change.
The app also respects the browser's preferred language when no selection has
been saved, and uses English as its final default.

Only the interface is translated. Student, classroom, course and module
names, entered notes, generated IDs, and saved marking-scheme names remain as
entered. The default preset's Thai category names remain Thai in both
interfaces. Save form and score changes before switching; the language action
reloads the page and is blocked while changes are unsaved.

## Files to edit yourself

- `locale/th/LC_MESSAGES/django.po`: Python and HTML, including labels,
  validation messages, paragraphs, and plural messages.
- `locale/th/LC_MESSAGES/djangojs.po`: spreadsheet and editor messages.

English is the source language; no separate English catalog is required.
A small set of illustrative translations and the supplied Thai labels are filled in. The other entries are blank
for you to translate. Most blank entries display the English source. Common strings and built-in
validation messages may already have a Thai translation bundled with Django.

Edit only the `msgstr` text to provide Thai, for example:

```po
msgid "Save module"
msgstr "บันทึกงาน"
```

Long paragraphs may span multiple quoted lines. Adjacent lines join together:

```po
msgid ""
"Upload a student list, check the preview, "
"and confirm the import when everything is correct."
msgstr ""
"อัปโหลดรายชื่อผู้เรียน ตรวจสอบข้อมูลตัวอย่าง "
"แล้วจึงยืนยันการนำเข้าเมื่อข้อมูลถูกต้อง"
```

Preserve placeholders such as `%(count)s`, `%(student_id)s`, and `%(label)s`.
You can reposition them, but do not change their names or remove them. They
represent values supplied at runtime. Keep relevant markup and escaped quotes
intact. Translation files are UTF-8.

Thai plural entries use one translation even when English has singular and
plural source text. Fill `msgstr[0]`; retain the existing Thai plural header.
Entries marked `#, fuzzy` are suggestions that need your review. Remove only
`fuzzy` after confirming the text; retain flags such as `python-format`.
Lines starting `#~` are obsolete entries and are not used by the application.

## Compile your changes

From the project folder after editing, on Mac:

```sh
.venv/bin/python manage.py compile_translations
```

On Windows:

```bat
.venv\Scripts\python.exe manage.py compile_translations
```

Restart the launcher, refresh the browser, and check the Thai pages. Compiled
`.mo` files are what the running app reads; editing `.po` alone does not change
what appears. Compilation checks message syntax and placeholder formats.

GNU gettext developer tools are needed to update or compile translations.
On Mac the commands also check the standard Homebrew gettext locations. On
Windows install GNU gettext and make its executables available on PATH.
Normal users do not need gettext: compiled catalogs ship with the app.

## When you add new interface text

Keep English source strings in the code and mark them for extraction.
Use explicit Django function names so the extractor can discover the text.

Python form labels/choices:

```python
from django.utils.translation import gettext_lazy
label = gettext_lazy("Student name")
```

Python messages during requests:

```python
from django.utils.translation import gettext
message = gettext("Student saved.")
```

HTML (load i18n in each template, after extends):

```html
{% load i18n %}
<h1>{% translate "Overview" %}</h1>
<p>{% blocktranslate trimmed %}A complete paragraph goes here.{% endblocktranslate %}</p>
```

JavaScript, after Django's catalog has loaded:

```javascript
gettext("Student name")
interpolate(gettext("Saved %(count)s score change(s)."), {count: 2}, true)
```

For dynamic Python messages, translate a literal string with named placeholders
and then substitute the values; do not pass an already formatted f-string to
gettext. HTML blocktranslate also supports named values and counts. Avoid
translating database keys, field names, numeric calculation values, URLs,
selectors, or user-entered content.

Extract new text from the project folder:

```sh
.venv/bin/python manage.py update_translations
```

On Windows substitute `.venv\Scripts\python.exe`. This updates both Thai files,
preserves existing translations, and excludes local data, generated assets,
bundled third-party scripts, tests, and migrations. Review fuzzy entries and
new blank entries, fill your translations, then run `compile_translations`.

## Distribution and testing

Include the whole `locale/` folder in clean source ZIPs and future desktop
bundles, including `.po` and compiled `.mo` files. Keep `app-data`, Python
virtual environments, backups, and generated runtime files out of clean ZIPs.
The current ZIP already contains the translation files and compiled examples.

Test switching both ways, reopening the app in the same browser, editing forms,
imports, long paragraphs, score paste/autofill, validation errors, and saves.
Many strings will remain English until you fill their Thai translations.
