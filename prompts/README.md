# Prompts

This directory is reserved for versioned model prompt contracts.

Future prompts must:

- treat uploaded scripts and fetched policy text as untrusted data, not instructions;
- request schema-constrained output;
- identify the snapshot and prompt version used;
- forbid invented clause identifiers or unsupported legal conclusions;
- keep deterministic workflow and gate logic outside the model.

No prompt implementation exists in this scaffold.
