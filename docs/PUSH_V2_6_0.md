# Push the v2.6.0 updates

Historical instructions. For the current release, use [Push v2.6.1](PUSH_V2_6_1.md).

The application version remains `2.6.0`. These commands push the branch while preserving the existing version tag.
The agent has not staged, committed, pushed or moved a tag.

Run from the project directory after reviewing the finished changes:

```sh
cd '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor'
git add --pathspec-from-file=docs/releases/v2.6.0-paths.txt
git diff --cached --stat
git commit -m "feat: standardize tutor output and add an MLX training pilot"
git push origin HEAD
```

The explicit path list includes the implementation, tests, research and public/synthetic verification evidence.
It excludes unrelated generated study content, learner state, private local configuration and the SSD model files.
Review any changes already staged before running the commit; a commit includes the entire staging area.

Training artifacts and model weights remain under `/Volumes/External SSD TB4/LocalAI`. They are not part of this
Git push. Model provenance, checksums and the experiment's limitations are in [the model card](STEM_TUTOR_MODEL.md).
The [decision log](benchmarks/2026-10-26-stem-model-pilot/decisions.md) records the compatibility experiments,
preservation choices and the decision not to promote the model.
