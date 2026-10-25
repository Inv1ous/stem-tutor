# Consistent STEM tutor output

Status: approved and implemented on 25 October 2026; see the plan for verification evidence.

The full inventory, proposed design, alternatives, response-type rules, mathematical examples, preservation
boundaries, acceptance checks and research sources are in [STEM output formatting](../../STEM_OUTPUT_FORMATTING.md).
The complete installed character/command maps are in
[the character catalogue](../../STEM_OUTPUT_CHARACTER_CATALOGUE.json).

The recommended design is one provider-neutral visual-writing contract with separate terminal and Obsidian adapters.
It uses semantic italic variables, font-tested scripts, explicit fallbacks for unsupported terminal maths, protected
literal spans and safe incremental rendering. It preserves mathematical meaning, machine-readable values, learner
text, speech, provider routing, model settings and local preload behaviour.

The user approved the linked design and requested implementation. Review clarified terminal-only fallbacks,
bounded streaming buffers and a required successfully rendered regression corpus; these preserve the approved scope.
