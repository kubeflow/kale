# Changelog

All notable changes to this project will be documented in this file.

## [2.3.0] - 2026-09-25

### Bug Fixes

- *(ci)* Pin Yarn so Dependabot lockfile updates match jlpm (#933)
- *(ci)* Scope PR title check concurrency to the pull request (#932)
- *(frontend)* Track the active notebook in state so the Enable toggle appears immediately (#962)
- *(frontend)* Add PVC mode in UI, UI RWO warning and documentation of volumes in Kale (#949)
- Pass the root notebook's parameters into its references (#959)

### Build

- *(deps)* Bump mermaid from 11.15.0 to 11.16.1 in /labextension/ui-tests (#927)
- *(deps)* Bump js-yaml from 3.15.0 to 3.15.1 in /labextension (#928)
- *(deps)* Bump mermaid from 11.15.0 to 11.16.1 in /labextension (#930)
- *(deps)* Bump nanoid from 3.3.17 to 3.3.18 in /labextension (#940)
- *(deps)* Bump tornado from 6.5.7 to 6.5.8 (#951)
- *(deps)* Bump postcss-selector-parser from 6.1.2 to 6.1.4 in /labextension (#952)
- *(deps)* Bump nanoid from 3.3.11 to 3.3.18 in /labextension/ui-tests (#953)
- *(deps)* Bump browserslist from 4.28.1 to 4.28.8 in /labextension (#954)
- *(deps)* Bump mistune from 3.3.0 to 3.3.3 (#955)
- *(deps)* Bump fast-uri from 3.1.5 to 3.1.7 in /labextension (#956)
- *(deps)* Bump @humanfs/node from 0.16.7 to 0.16.8 in /labextension (#957)
- *(deps)* Bump js-yaml from 3.15.1 to 3.15.2 in /labextension (#964)
- *(deps)* Bump anyio from 4.12.1 to 4.14.2 (#967)

### Features

- Add a way to mount PVCs into Pipeline (#907)
- Add notebook: cell type for multi-notebook composition. (#867)
- Add searchable runtime image selection (#939)
- *(backend)* Support KALE_KFP_NAMESPACE for configurable KFP server namespace (#875)
- Add Kubernetes Secrets as environment variables to pipeline steps (#891)
- Update compile button to run immediately when a new option is picked (#971)

### Miscellaneous

- *(examples)* Update Examples to hide HTML reports that have no output (#926)
- Add latest news about Kubeflow Kale releases (#931)
- *(backend)* Move nbprocessor constants into a separate module (#909)
- *(examples)* Adding Small Language Models fine-tuning example (#941)

### Other

- Bump dev version to 2.2.1a1 (#922)

Signed-off-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>
Co-authored-by: ederign <531351+ederign@users.noreply.github.com>
