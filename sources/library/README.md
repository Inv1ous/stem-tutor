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

## Copyright

Keep only material you obtained legally and use for your own study. The PDFs and the cache are ignored by git and are
never published. The workers use the library as a reference and teach in the chapter's own words.
