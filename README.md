# Jupyter2Crate to Transfer Jupyter Notebooks into RO-Crates

This repository contains the source code of a infrastructure-based approach to transfer Jupyter Notebooks into a [Research Object Crates (RO-Crates)](https://w3id.org/ro/crate/1.1) bundle whereas the semantic model rerpresents retrospective provenance about the notebook.

**Note that this software is a research prototype and may contain bugs and errors, i.e., do not use this in production.**

The approach has been used in order to create the RO-Crates at: TBD

The approach is described in full detail in this article:

TBD

## License

[![Creative Commons License](https://i.creativecommons.org/l/by/4.0/88x31.png)](http://creativecommons.org/licenses/by/4.0/)

This work is licensed under a [Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/).

In order to reference this software, please consider the information in the [CITATION.cff](CITATION.cff) file.

## Usage

### Software Requirements

....

### Running

In order to run the source code, install the python dependencies from `requirements.txt` and make sure that [Docker](https://www.docker.com/) is installed and running.
To disable the use of siegfried, put `None` when initializing `ELN2Crate` in the parameter `SIEGFRIED_IMAGE` (see below).

A minimum running example is as follows:

```python3
model = Jupyter2Crate(LOGGER, NAMESPACE_URL, NB_PATH)

try:
    model.write_files()
    model.create_model()
    model.write_crate('./ro-crate_%s' % (NB_PATH.replace('.ipynb', '')))
except NBNotFound as e:
    print('Notebook was not found: ' + str(e), file=sys.stderr)
```

where the following variables have been set:

* `LOGGER` contains an initialized python-logger using the package `logging`
* `NAMESPACE_URL` is the base URL of the namespace of the semantic model
* `NB_PATH` the path to the notebook that should be bundled
