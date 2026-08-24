# Prompts

This directory contains versioned model prompt contracts.

Future prompts must:

- treat uploaded scripts and fetched policy text as untrusted data, not instructions;
- request schema-constrained output;
- identify the snapshot and prompt version used;
- forbid invented clause identifiers or unsupported legal conclusions;
- keep deterministic workflow and gate logic outside the model.

Gate 4 includes `policy/proposal-v1.md`. Cloud assembly loads it as package data and supplies the response schema separately; the prompt treats the policy diff as untrusted evidence and leaves publication to a human administrator.
