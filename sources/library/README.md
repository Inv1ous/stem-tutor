# The sources library

Your own textbooks, class notes, mark schemes and worksheets, as PDFs, for the AI workers (the content foundry and
the refine system) to look things up in while they write and check chapters.

## Adding to it

Drop PDFs into any subfolder with any name and any depth, for example `My Notes/Chemistry/Electrolysis.pdf` or
`Maths Textbook Ch3/Quadratics.pdf`. Spaces and accents are fine. There is nothing to register or index: the tool
finds new and changed files the next time it runs.

## How the workers use it

All read-only, from the repo root (quote any path with spaces):

```
.venv/bin/python build/library.py tree [folder]
.venv/bin/python build/library.py search "<terms>" [--folder NAME-FRAGMENT] [--root library|papers|specs|all] [--max N]
.venv/bin/python build/library.py text <pdf path or unique name fragment> [--pages 3-5] [--all]
.venv/bin/python build/library.py for <subtopic id, e.g. 9702-5.1>
```

`search` ignores case and accents and ranks pages by how many of your words they contain and how close together.
`for` turns a chapter's knowledge components into searches and lists the best pages for each. The first search of a
big library reads every PDF once (progress shows on screen); later searches use the cache in `.cache/`, which is
rebuilt for any file that changes. A scanned PDF with no text layer is reported as needing OCR and skipped.

`--root papers` and `--root specs` search the downloaded past papers and syllabuses too; `library` is the default
and the only one that is yours.

## Figures

Textbooks have diagrams, apparatus and graphs worth having in a chapter. The workers can find, look at and crop them:

```
.venv/bin/python build/library.py figures <pdf> [--pages a-b]      candidates, one line each: id · page · kind · caption · box
.venv/bin/python build/library.py page <pdf> <n> [--dpi 110] [--box x0,y0,x1,y1]    a PNG of the page, to look at
.venv/bin/python build/library.py crop <pdf> --page N --box x0,y0,x1,y1 --to <spec>/<name> [--dpi 200]
                                   [--caption "…"] [--for <subtopic>] [--kc <id>] [--why "…"]
.venv/bin/python build/library.py extract <pdf> --page N --index K --to <spec>/<name>   an embedded image, unscaled
```

`figures` lists embedded images, captions ("Figure 3.2", "Fig. 4", "Table 2", "Diagram", "Graph") with a proposed crop box
(the region next to the caption up to the neighbouring text), and pages that are mostly drawing. Tiny images and an image
repeated on several pages (a logo) are listed as `skip: decorative`. A box is four fractions (0-1) of the page as it is
shown (after any rotation, cut to the CropBox), so it does not depend on the dpi; positions of embedded images are not
known to poppler, so use `page` to look and `extract` or a box. The worker opens the PNG that `page` writes (in
`.cache/pages/`) before deciding.

`crop` trims the empty margins, refuses a result under 150x100 px or over 6 MB, never overwrites, and writes
`build/out/assets/<spec>/<name>.png` plus `<name>.png.json` (the PDF, page, box, dpi, checksum, caption, chapter, why, time).
It prints the lines to paste into the note: `![[Assets/<spec>/<name>.png]]` and `*Figure: … (source: <pdf>, p.N)*`.
A gate checks that the file, the checksum and that source line are there. Publishing copies the PNG into your vault's
`Assets/`.

These images come from your own PDFs, for your private study. `build/out/assets/` is ignored by git: they are never
committed, and the vault copy stays on your machine. Do not share the vault or the images.

## Copyright

Keep only material you obtained legally and use for your own study. The PDFs and the cache are ignored by git and are
never published. The workers use the library as a reference and teach in the chapter's own words.
