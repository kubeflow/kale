# Copyright 2026 The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Marshal dispatcher and backend base class.

Defines :class:`MarshalBackend`, the abstract base class for type-aware
serializers that Kale uses to pass data between pipeline steps, and
:class:`Dispatcher`, which routes objects to the correct backend at
save/load time.
"""

import logging
import os
import re
from typing import Any

from kale.common import utils

log = logging.getLogger(__name__)

__DATA_DIR = os.path.curdir


def set_data_dir(path):
    """Set the data directory where marshalling happens."""
    global __DATA_DIR
    __DATA_DIR = path
    # create dir if not exists
    if not os.path.isdir(__DATA_DIR):
        os.makedirs(__DATA_DIR, exist_ok=True)


def get_data_dir():
    """Get the data directory where marshalling happens."""
    global __DATA_DIR
    return __DATA_DIR


class MarshalBackend:
    """Base class for marshalling Python objects.

    This class is supposed to be subclassed by specialized backends that
    implement the `save` and `load` functions to marshal library-specific
    objects.

    A backend registers itself to specific objects/file types using the
    following class attributes:

    * `file_type`: The file extension of the files/folders the backend is able
                   to restore. NOTE: Currently this can be just *one* ext.
    * `obj_type_regex`: A regex which is matched against the `type` of an
                        object.

    Take a look at `backend.py` for some examples on how to create custom
    marshal backends.
    """

    name: str = "Default backend"
    display_name: str = "generic"  # This is supposed to tbe the library name
    file_type: str = "dillpkl"
    obj_type_regex: str = None
    predictor_type: str = None  # Used for creating serving predictors

    # Set to False if you want your backend not to use the default backend
    # in case of a missing library.
    fallback_on_missing_lib = True

    def __init__(
        self,
        name: str = None,
        display_name: str = None,
        obj_type_regex: str = None,
        file_type: str = None,
    ):
        self.name = name or self.name
        self.display_name = display_name or self.display_name
        self.obj_type_regex = obj_type_regex or self.obj_type_regex
        self.file_type = file_type or self.file_type

    def wrapped_save(self, obj: Any, name: str):
        """Wrapper around the public `save` function.

        This function provides common logging and exception handling for every
        class that extends the base `MarshalBackend`. `Dispatcher` calls
        directly this function instead of `save`.

        Returns the path (<data_dir>/<basename>.<backend_extension>) to the
        saved file.
        """
        abs_path = os.path.join(get_data_dir(), name + "." + self.file_type)
        log.debug(
            "Saving %s object using %s: %s to %s", self.display_name, self.name, name, abs_path
        )
        try:
            self.save(obj, abs_path)
        except ImportError as e:
            if not self.fallback_on_missing_lib:
                raise e
            log.warning(
                "Failed to import %s (%s). Falling back to default backend.", self.display_name, e
            )
            self._default_save(obj, abs_path)  # always try the default save
        return abs_path

    def save(self, obj: Any, path: str):
        """Save `obj` to file."""
        self._default_save(obj, path)

    @staticmethod
    def _default_save(obj: Any, path: str):
        import dill

        with open(path, "wb") as f:
            dill.dump(obj, f)

    def wrapped_load(self, name: str) -> Any:
        """Wrapper around the public `load` function.

        This function provides common logging and exception handling for every
        class that extends the base `MarshalBackend`. `Dispatcher` calls
        directly this function instead of `load`.
        """
        abs_path = os.path.join(get_data_dir(), name + "." + self.file_type)
        log.debug("Loading %s file using %s: %s", self.display_name, self.name, name)
        try:
            return self.load(abs_path)
        except ImportError as e:
            if not self.fallback_on_missing_lib:
                raise e
            log.warning(
                "Failed to import %s (%s). Falling back to default backend.", self.display_name, e
            )
            return self._default_load(abs_path)  # always try the default load

    def load(self, file_path: str) -> Any:
        """Restore `file_path` to memory."""
        return self._default_load(file_path)

    @staticmethod
    def _default_load(file_path: str) -> Any:
        import dill

        with open(file_path, "rb") as f:
            return dill.load(f)


dispatcher = None


def get_dispatcher():
    """Get the unique instance of dispatcher.

    This is preferred since Dispatcher registered all MarshalBackends that
    are decorated with the `register` function. We don't want the registration
    process to happen all the time.
    """
    global dispatcher
    if not dispatcher:
        dispatcher = Dispatcher()
    return dispatcher


class Dispatcher:
    """Dispatch backend classes based on obj types or file extensions.

    This class holds a reference to all the marshalling backends that register
    themselves with the `register` function. `Dispatcher` is the main mechanism
    with which a specialized backend is chosen to either save or load an
    and object to/from memory.

    The public functions that users should be aware of:

    * `save`: Dispatches to a specialized backend based on the input object
              type, by filtering through the backends' `obj_type_regex`
              attribute.
    * `load`: Dispatches to a specialized backend based on the input file path
              by filtering through the backends' `file_type` attribute.

    Users and external code are not supposed to interact directly with the
    singleton instance of this class. Rather, they should just call the
    two publicly exposed functions `save` and `load` like so:

    ```
    from kale.marshal import save, load
    ```
    """

    END_USER_EXC_MSG = (
        "\n\nThe error was:\n%s\n\nPlease help us improve Kale"
        " by opening a new issue at:"
        "\nhttps://github.com/kubeflow-kale/kale/issues."
    )

    def __init__(self):
        self.backends: dict[str, MarshalBackend] = {}

    def register(self, cls: type[MarshalBackend]) -> type[MarshalBackend]:
        """Register a new marshalling backend.

        Args:
            cls: Marshal backend class

        Returns: the class itself
        """
        if cls.__name__ not in self.backends:
            self.backends[cls.__name__] = cls()
        return cls

    def get_backend(self, obj: Any):
        """Get the backend registered for the input object type."""
        return self._dispatch_obj_type(obj)

    def get_backends(self) -> dict[str, MarshalBackend]:
        """Get all registered backends."""
        # FIXME: How can we make this dict readonly? We don't want external
        # code to mess with it.
        return dict(self.backends)

    def get_backend_by_name(self, name: str):
        """Get a registered backend by its display name."""
        return self.backends[name]

    def save(self, obj: Any, obj_name: str):
        """Save an object to file.

        Args:
            obj: Object to be marshalled
            obj_name: Name of the object to be saved
        """
        try:
            return self._dispatch_obj_type(obj).wrapped_save(obj, obj_name)
        except Exception as e:
            error_msg = (
                "During data passing, Kale could not marshal the"
                f" following object:\n\n  - path: '{obj_name}'\n  - type: '{type(obj)}'"
            )
            log.error(error_msg + self.END_USER_EXC_MSG % e)
            log.debug("Original Traceback", exc_info=e.__traceback__)
            utils.graceful_exit(1)

    def load(self, basename: str):
        """Restore a file to memory.

        Args:
            basename: The name of the serialized object to be loaded

        Returns: restored object
        """
        try:
            entry_name = self._unique_ls(basename)
            return self._dispatch_file_type(entry_name).wrapped_load(basename)
        except Exception as e:
            error_msg = (
                "During data passing, Kale could not load the"
                f" following file:\n\n\n  - name: '{basename}'"
            )
            log.error(error_msg + self.END_USER_EXC_MSG % e)
            log.debug("Original Traceback", exc_info=e.__traceback__)
            utils.graceful_exit(1)

    def get_path(self, basename: str):
        """Get a serialized kfp artifact abs path.

        Args:
            basename: The name of the artifact to retrieve its abs path

        Returns: the marshalled artifact path
        """
        return os.path.join(get_data_dir(), self._unique_ls(basename))

    @staticmethod
    def _unique_ls(basename: str):
        # get the unique file/folder inside _DATA_DIR: there could be
        # multiple files with the same name and different extension.
        entries = [
            ls
            for ls in os.listdir(get_data_dir())
            if (
                (
                    os.path.isfile(os.path.join(get_data_dir(), ls))
                    or os.path.isdir(os.path.join(get_data_dir(), ls))
                )
                and os.path.splitext(ls)[0] == basename
            )
        ]
        log.debug("Found %d entries for basename '%s': %s", len(entries), basename, entries)
        if not entries:
            log.debug(
                "Looking for unique file/folder with basename '%s' in %s", basename, get_data_dir()
            )
            raise ValueError(
                f"No file or folder found with basename '{basename}' in {get_data_dir()}"
            )
        if len(entries) > 1:
            raise ValueError(f"Found multiple files/folders with name {basename}: {entries}")
        return entries[0]

    def _dispatch_obj_type(self, obj: Any) -> MarshalBackend:
        """Dispatch to a backend based on the object's type matching regex.

        Args:
            obj: any Python object
        """
        # object types are printed as <class 'obj type'>
        _type = re.sub(r"'>$", "", re.sub(r"^<class '", "", str(type(obj))))
        # type of base class
        _type_base = re.sub(r"'>$", "", re.sub(r"^<class '", "", str(obj.__class__.__bases__[0])))
        _backends = [
            backend
            for backend in self.backends.values()
            if re.match(backend.obj_type_regex, _type)
            or re.match(backend.obj_type_regex, _type_base)
        ]
        if len(_backends) > 1:
            raise RuntimeError(
                "Too many matching marshalling backends for"
                f" object type {_type} (base type {_type_base}): {_backends}"
            )
        if not _backends:
            log.debug(
                f"No backends found for type {_type} ({_type_base}). Falling back to"
                " default backend."
            )
            return MarshalBackend()
        else:
            return _backends[0]

    def _dispatch_file_type(self, filename: str) -> MarshalBackend:
        """Dispatch to a backend based on the matching file type.

        Note: The "file" could be a folder. Some backends marshal an object
        inside a folder. That is why we don't explicitly check if the path
        points to a file and instead we just get the extension.

        Args:
            filename (str): filename whose extension must be matched.
        """
        _backends = [
            backend
            for backend in self.backends.values()
            if os.path.splitext(filename)[1].lstrip(".") == backend.file_type
        ]
        if len(_backends) > 1:
            raise RuntimeError(
                "Too many matching marshalling backends for"
                f" file {os.path.basename(filename)} : {_backends}"
            )
        if not _backends:
            log.debug(f"No backends found for '{filename}'. Falling back to default backend.")
            return MarshalBackend()
        else:
            return _backends[0]
