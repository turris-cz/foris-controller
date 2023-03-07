# Foris Controller {{ cookiecutter.name }} module

This is a {{ cookiecutter.name.lower() }} module for foris-controller

## Requirements

- python3
- foris-controller
- tox (optional; for tests and linters)

## Installation

```
pip install .
```

## Running tests

### Get tox.ini from shared submodule

```
git submodule add https://gitlab.nic.cz/turris/foris-controller/common.git common
ln -s common/foris-controller-modules/tox.ini .
```

### Run the tests

```
tox -q -e py39
```
