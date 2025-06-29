# Heatchmap - A package for estimation and visualization of hitchhiking quality.

[![PyPI version](https://badge.fury.io/py/heatchmap.svg)](https://badge.fury.io/py/heatchmap)

## Prerequisites

The up-to-date raw map is [on huggingface](https://huggingface.co/datasets/Hitchwiki/hitchhiking-heatmap), the model used to calculate it can be found there [as well](https://huggingface.co/Hitchwiki/heatchmap-models).

Both - model and map - are updated monthly using the latest data from `hitchmap.com`. The update is performed by running [this script](https://github.com/Hitchwiki/hitchhiking-heatmap-generator).

## Just getting the map
With the above prerequisites still running you can get the latest map with the code shown in https://github.com/Hitchwiki/hitchhiking.org which will result in the map on https://hitchhiking.org.


## Installation

You can install the `heatchmap` package from PyPI:

```bash
pip install heatchmap
```

### Linting

We use Ruff for linting [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/).

The settings can be found in `ruff.toml`.

To configure automatic linting for VS Code check out the extension [https://github.com/astral-sh/ruff-vscode](https://github.com/astral-sh/ruff-vscode).

## Usage

Here are some usage examples for the `heatchmap` package:

- https://github.com/Hitchwiki/hitchhiking-heatmap-generator

## Contributing

If you want to build predictive models related to hitchhiking (e.g. waiting time) you are welcome get get started experimenting [here](https://github.com/Hitchwiki/hitchhiking-data/tree/main/visualization). If you show promising results your models can be integrated into this package as well.
