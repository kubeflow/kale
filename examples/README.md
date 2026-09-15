# Examples

This folder contains a list of curated examples that showcase how Kale can
support an end-to-end data science experience on Kubeflow.

Some of these have a companion Codelab that can help you getting started:

- Titanic Example [Codelab](https://codelabs.developers.google.com/codelabs/cloud-kubeflow-minikf-kale/#0)

## Multi-notebook composition

[`composition/`](composition/) shows how one notebook references another with a
`notebook:` cell, so several notebooks compile into a single pipeline. It ships
two entry points, one composed purely of references and one that adds a step of
its own. See its [README](composition/README.md).
