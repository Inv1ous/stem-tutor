# Push v2.6.1

The application, plugin and release logs are prepared for **2.6.1**. These commands create a new release commit and
annotated tag, then push `main` and only that tag atomically. The existing v2.6.0 tag is preserved.
The release preparation did not commit, tag or push anything. The current staging area already contains release changes,
including the removed font/source paths. The refreshed path list omits those already-staged deletions so rerunning
the command succeeds; their deletions remain staged and will be included in the commit.

```sh
cd '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor' &&
git --literal-pathspecs add -A --pathspec-from-file=docs/releases/v2.6.1-paths.txt &&
git diff --cached --stat &&
git commit -m "chore(release): prepare v2.6.1" &&
git tag -a v2.6.1 -m "STEM Tutor v2.6.1" &&
git push --atomic origin main refs/tags/v2.6.1
```

The path list includes code, tests, project workflow configuration, release documentation and migration adapters. It excludes `.DS_Store`, personal
agent settings, generated study builds, Library payloads and worker-state contents. Git records symlinks without
following them into the sibling Library or Work folders. Any already-staged changes are also included in a commit;
inspect `git diff --cached` before committing if the staging area has changed since preparation.

The sibling `STEM Tutor/Library`, `Work`, `Archive` and SSD models stay local and require a separate backup.
The release does not claim all source pages are extracted or approve pending candidates. See [release notes](releases/v2.6.1.md).
