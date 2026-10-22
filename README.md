# Jupyter2Crate to Transfer Jupyter Notebooks into RO-Crates

This repository contains the source code of an infrastructure-based approach to transfer Jupyter Notebooks into a [Research Object Crates (RO-Crates)](https://w3id.org/ro/crate/1.1) bundle whereas the semantic model represents retrospective provenance about the notebook.

**Note that this software is a research prototype and may contain bugs and errors, i.e., do not use this in production.**

The approach has been used in order to create the RO-Crates at: https://github.com/m6121/Infrastructure-based-Provenance-Tracking

The approach is described in full detail in this article:
TBD

## License

This work is licensed under the [MIT License](LICENSE).

In order to reference this software, please consider the information in the [CITATION.cff](CITATION.cff) file.

## Usage

### Software Requirements

Installation of the python package is required, e.g. by installing via pip:

```bash
pip install git+https://github.com/m6121/Jupyter2Crate.git
```

### Running

A minimum running example transforms a Jupyter notebook into an RO-Crate is as follows:

```python3
import logging
import os
import sys
from pprint import pprint

from jupyter2crate import Jupyter2Crate, NBNotFound

script_path = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_path, 'jupyter2crate.log')
if os.path.isfile(log_path):
    os.remove(log_path)

logging.basicConfig(filename=log_path, format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s')
logger = logging.getLogger('jupyter2crate')
logger.setLevel(logging.DEBUG)

# URL of the provenance namespace
NAMESPACE_URL = "https://provenance.example.org/jupyter"

NOTEBOOK_PATHS = [
    "Analysis.ipynb",
]

for NB_PATH in NOTEBOOK_PATHS:
    model = Jupyter2Crate(logger, NAMESPACE_URL, NB_PATH)

    try:
        model.write_files()
        model.create_model()
        model.write_crate('./ro-crate_%s' % (NB_PATH.replace('.ipynb', '')))
    except NBNotFound as e:
        print('Notebook was not found: ' + str(e), file=sys.stderr)
```
