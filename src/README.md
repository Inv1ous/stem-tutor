# Canonical tutor engine

`src/tutorlib/` owns the tutor engine's Python source. The terminal launcher adds
`src/` to its import path. Course preparation and older plugin entry points remain
compatible through the relative `tutorlib` symlink in
`plugin/stem-tutor/skills/tutor/scripts/`.

The symlink is an adapter, not a second source copy. Change engine modules here.
Publishing continues to materialize the scripts tree, following that adapter, so
the installed `.tutor/engine/tutorlib/` directory contains regular files and works
without access to the checkout. The wheel dependencies remain in the plugin's
`scripts/wheels/` distribution directory and are copied alongside the installed
engine. No learner vault is changed by moving source files.

Runtime discovery preserves explicit `STEM_TUTOR_VAULT` selection and the existing
mounted-vault checks. The source checkout can use `build/diagrams.py`; an exported
engine without that optional renderer keeps the existing fallback to words.
