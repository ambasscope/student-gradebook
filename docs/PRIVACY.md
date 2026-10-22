# Privacy information

Student Gradebook is designed for local use. The application's own code stores
teacher details, student lists, attendance, marks and comments in a local SQLite
database. It contains no account server or student-data upload service.

The internal server binds to the local loopback interface. The embedded desktop
window connects to that local server. The source launcher's first setup uses the
internet to install dependencies; downloading updates and opening external links
also use the network. Microsoft Edge WebView2 is a separate Microsoft runtime. It collects required
diagnostic data and can collect optional diagnostics based on Windows privacy
settings. Its SmartScreen and crash-reporting features can send information to
Microsoft as described in Microsoft's WebView2 privacy guidance and privacy
statement. These runtime behaviors are separate from the gradebook's own local
record storage.

Import previews are temporarily stored in the installation's database-backed
session and expire. Generated reports are written or downloaded to the location
chosen by the user. Backups and diagnostic logs remain in the local data folder.
For data paths and transfer instructions, see the README.

Users control access to their computer, data folder, backups and exported files.
An application update does not send their records to the source-code repository.
Only clean source and clean build artifacts are intended for public distribution.

[Microsoft WebView2 privacy guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/data-privacy)

[Microsoft Privacy Statement](https://privacy.microsoft.com/privacystatement)
