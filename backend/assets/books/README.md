# Bundled Example Books

Place production example books in this directory so they are packaged with the backend Docker image.

Supported formats:
- `.pdf`
- `.epub`
- `.txt`

Discovery behavior:
- The backend scans `backend/assets/books/` first.
- It also scans `backend/books/` as a secondary fallback.
- Example keys are derived from the filename stem (slug format).

Dune example:
- Include a file whose stem resolves to `dune` (for example: `Dune.pdf`), or keep a filename containing `Dune` and use the current endpoint key mapping.
