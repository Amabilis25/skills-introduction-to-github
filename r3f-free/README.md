# R3F-FREE — neutralized same-model behavioral campaign

This branch contains a **public, neutralized evaluation harness only**. It does not contain META AD-COGNITUS source code, registries, bindings, manifests, private datasets, or runtime packages.

The experiment generates three outputs for each of 18 tasks under the same open model and identical decoding parameters. The only treatment difference is the precompiled cognitive instruction:

- `NONE`
- `SELECTIVE`
- `ORACLE_FORMS`

The model never receives the arm label. Generation order is randomized. Blind evaluation is performed from a separate artifact that excludes the condition mapping; unblinding must happen only after scoring.

## Compute policy

The workflow uses a standard GitHub-hosted runner in this public repository and downloads a public Apache-2.0 model. It requires no API key, no paid inference endpoint, and no external compute credit.

## Model

Default: `Qwen/Qwen2.5-0.5B-Instruct`. The workflow resolves the current repository commit once at the start of the run, records it, and downloads that exact revision for all 54 generations.

## Artifacts

- `r3f-free-blind-bundle`: outputs + rubrics, without condition labels.
- `r3f-free-mapping`: condition mapping, to be opened only after blind scoring.
- `r3f-free-runs`: full run records and generation receipt.
