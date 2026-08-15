"""
Formality classifier training.

The training entry point is :mod:`classifier.train`. It is deliberately not
imported here: this module used to *be* the training script, so importing the
package ran a CUDA probe, printed to stdout, and pulled in torch — even for
callers that only wanted something else in the same directory.

    python -m classifier.train --help
"""

__all__ = ["train"]
