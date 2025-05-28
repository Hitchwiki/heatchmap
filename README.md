# Heatchmap - A package for estimation and visualization of hitchhiking quality.

[![PyPI version](https://badge.fury.io/py/heatchmap.svg)](https://badge.fury.io/py/heatchmap)

## Prerequisites

The up-to-date raw map is [on huggingface](https://huggingface.co/datasets/tillwenke/heatchmap-map), the model used to calculate it can be found there [as well](https://huggingface.co/tillwenke/heatchmap-model).

Both - model and map - are updated monthly using the latest data from `hitchmap.com`. The update is performed using this packege in a [huggingface space](https://huggingface.co/spaces/tillwenke/heatchmap-space) which is triggered from out side via [GitHub actions](https://github.com/tillwenke/heatchmap-space-scheduler/tree/main).

## Just getting the map
With the above prerequisites still running you can get the latest map as shown in https://github.com/Hitchwiki/hitchhiking.org.


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

```python
import heatchmap

# Example usage
# Add your usage examples here
```

## Contributing

If you want to build predictive models related to hitchhiking (e.g. waiting time) you are welcome get get started experimenting [here](https://github.com/Hitchwiki/hitchmap-data/tree/main/visualization). If you show promising results your models can be integrated into this package as well.
