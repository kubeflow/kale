## FAQ

Maybe not "frequently asked", but hopefully these answers will be useful.

### Exception `ModuleNotFoundError` in pipeline step

This happens most often with people trying out Kale the first time. For
instance, if you are running the Titanic example, your first step of the
pipeline might fail with: `ModuleNotFoundError: No module named 'seaborn'`.

Kale **does not take care of building a new docker image** with your
data/installation's dependencies, when running the pipeline. Developing a
notebook in a Kubeflow's notebook server, means that you will be installing new
packages or downloading and creating new data that are essential for the
execution of your code. The dependencies now live inside the volume[s] mounted
on the pod running your notebook server. When converting the notebook to a new
pipeline, Kale uses the configured default base image (JupyterLab setting,
``KALE_DEFAULT_BASE_IMAGE``, or ``python:3.12``) unless a step declares its
own ``image:`` tag, so all those incremental changes (e.g. new
installations) will be lost.

### Data passing and pickle errors

Part of the Kale magic is to recognise the data dependencies between the cells
and have the resulting pipeline steps marshal automatically those objects. In
Python many objects can be marshalled using libraries like `pickle` or `dill`,
but this general approach is not universal.

Some objects require specialised functions. This is often the case in machine
learning libraries, where saving and loading a model requires library-specific
code (e.g. `model.save()`, `xx.load('model.xx')`). Kale implements a marshalling
module that inspects run-time the type of the objects that need to be passed
between pipeline steps and dispatches the save/load calls to specific backend,
falling back to using `dill` when an object type is not recognised.

This means that, in case you see errors related to pickle failing to save a
particular object at the end of a pipeline step, Kale needs to implement a
specific backend to save that object (if possible). This system was build to be
easily extensible, you can take a look [here](kale/marshal/backends.py)
at existing backends and open a new issue to request for the new backend to be
implemented.

### Compiler errors

When compiling your notebook you may encounter the following error:
```
Internal compiler error: Compiler has produced Argo-incompatible workflow.
Please create a new issue at https://github.com/kubeflow/pipelines/issues attaching the pipeline code and the pipeline package.
```
followed by some explanation. For example:
```
Error: time="2020-10-12T17:57:45-07:00" level=fatal msg="/dev/stdin failed to parse: error unmarshaling JSON: while decoding JSON: json: unknown field \"volumes\""
```

This is an error raised by the KFP compiler. Kale compile process contains
converting to KFP DSL and then compiling it, so it triggers the KFP compiler.

The KFP compiler runs `argo lint` on the generated workflow, if it finds the
`argo` executable in your environment's `PATH`.

To overcome this issue, you could either remove `argo` from your `PATH` or
replace it with a version that is supported by KFP. At the time of writing this
section, the recommended version is 2.4.3. Follow [this
link](https://github.com/argoproj/argo/releases/tag/v2.4.3) to get the proper
binary.

## Limitations

All the magic provided by Kale is possible thanks to the dynamic nature of
Python, on our ability to statically analyse the source code and take actions
dynamically at run-time to properly marshal objects between pipeline steps. But
this is a double-edge sword as Kale cannot introspect and cover some corner
cases, you should take care not to write code that falls into the following
examples, least risking unintended behaviour in the execution of the pipeline.

### Aliasing

```python
# Cell 1 - Step A:
model1 = model2 = SomeModel()

# -------------------------

# Cell 2 - Step B (dep on A):
model2.addLayer(SomeLayer())

# -------------------------

# Cell 3 - Step C (dep on B):
print(model1)
```

**Expected**:
Step C loads an object with name `model1`, but with value changed from StepB
(`model2`).

**What Happens**:
Step A saves both `model1` and `model2`. Step C loads `model1`, an object
without the additional layer introduced by Step B

### Mutating global state

```python
# Cell 1 - Imports
import warnings

# -------------------------

# Cell 2 - Step A
warnings.simplefilter("ignore")
warnings.warn("A", DeprecationWarning)

# -------------------------

# Cell 3 - Step B (dep on A)
warnings.warn("B", DeprecationWarning)
```

**Expected**:
No warnings should not be emitted.

**What happens**:
Warning `B` is emitted.

**Solution**:
Global state should not be mutated during the pipeline execution, as there could
be multiple steps depending on it. Instead, configure all global state in a
**global** cell and not change it dynamically.

The above should be written like this:

```python
# Cell 1 - Imports
import warnings
warnings.simplefilter("ignore")

# -------------------------

# Cell 2 - Step A
warnings.warn("A", DeprecationWarning)

# -------------------------

# Cell 3 - Step B (dep on A)
warnings.warn("B", DeprecationWarning)
```

### Passing non-serialisable objects between steps

```python
# Cell 1 - Step A
f = open("myfile", "a")

# -------------------------

# Cell 2 - Step B (dep on A)
f.write("B")

# -------------------------

# Cell 3 - Step C (dep on B)
f.write("C")
f.close()
```

**Expected**:
`BC` should be written to `myfile`.

**What happens**:
Step A will try to save variable `f` and fail.

**Solution**:
If you _really_ need to be using a non-serialisable object (e.g., files,
sockets, locks etc) in multiple steps, initialise it from scratch each time,
either by adding the code in a global cell, or in a function that is called each
time. For example:

```python
Cell 1 - Functions
def get_my_file():
    return open("myfile", "a")

# -------------------------

Cell 2 - Step A
with get_my_file() as f:
    f.write("B")

# -------------------------

Cell 3 - Step B (dep on A)
with get_my_file() as f:
    f.write("C")
```

### Star imports

```python
# Cell 1 - Imports
from mymodule import *

# Cell 2 - Step A
# function defined inside `mymodule`
res = myfoo()
```

Kale cannot possibly know that `myfoo` is a valid name that is defined inside
`mymodule`, so it will try to marshal it. In general, any `import *` statement
can cause these issue, apart from when the code that uses these imports lives in
the same step as the import statement itself.
