"""perfectshape: baskets and basket ratios that trace a clean shape (trend, range) ending today."""

import os as _os

# The search runs its own threads, one per core (perfectshape.parallel). A multi-threaded BLAS under each of
# them would start cores x cores threads, and its threading only slows the small products used here, so BLAS
# runs one thread per caller unless the environment says otherwise. Set before numpy is first imported.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_var, "1")
