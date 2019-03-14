import logging
from typing import Any, BinaryIO, Iterable, List, Mapping, NamedTuple, Optional, Union

from modelforge import Model

from lookout.core.api.event_pb2 import ReferencePointer as ApiReferencePointer
from lookout.core.api.service_analyzer_pb2 import Comment
from lookout.core.ports import Type


class ReferencePointer(NamedTuple("ReferencePointer", (("url", str),
                                                       ("ref", str),
                                                       ("commit", str)))):
    """
    We redefine ReferencePointer because Protocol Buffers message objects suck.
    """

    @staticmethod
    def from_pb(refptr: ApiReferencePointer) -> "ReferencePointer":
        """
        Convert from ReferencePointer defined in protocol buffers to our own Python-friendly \
        pointer.
        """
        return ReferencePointer(*[f[1] for f in refptr.ListFields()])

    def to_pb(self) -> ApiReferencePointer:
        """
        Convert to ReferencePointer defined in protocol buffers.
        """
        return ApiReferencePointer(internal_repository_url=self.url,
                                   reference_name=self.ref,
                                   hash=self.commit)


class AnalyzerModel(Model):
    """
    All models used in `Analyzer`-s must derive from this base class.
    """

    NAME = Model.GENERIC_NAME
    VENDOR = "<unknown>"
    DESCRIPTION = "<unknown>"

    def __init__(self, log_level: int = logging.INFO, **kwargs):  # noqa: D401
        """
        Prepare a dummy instance of the model. We expect that `load()` or `construct()` will be \
        called afterwards.

        Defines:
        `name` - name of the model. Corresponds to the bound analyzer's class name and version.
        `ptr` - state of the Git repository on which the model was trained.
        :param log_level: Logger's verbosity.
        :param kwargs: passed to the upstream's `__init__`.
        """
        super().__init__(log_level=log_level)
        self.ptr = ReferencePointer("<unknown url>", "<unknown reference>", "<unknown commit>")

    @classmethod
    def generate(cls, analyzer: Type["Analyzer"], ptr: ReferencePointer) -> "AnalyzerModel":
        """
        Initialize the model (`__init__` does not do the real work to allow `load()`).

        :param analyzer: Bound type of the `Analyzer`. Not instance!
        :param ptr: Git repository state pointer.
        :return: self
        """
        assert issubclass(cls, analyzer.model_type)

        class RealModel(cls):
            NAME = analyzer.name
            VENDOR = analyzer.vendor
            DESCRIPTION = "Model bound to %s Lookout analyzer." % analyzer.name

        RealModel.__name__ = analyzer.name
        model = RealModel()
        model.derive([analyzer.version])
        model.ptr = ptr
        return model

    def dump(self) -> str:
        """
        Satisfy the upstream's abstract method.

        :return: summary text of the model.
        """
        return "%s/%s %s %s" % (self.name, self.version, self.ptr.url, self.ptr.commit)

    def save(self, output: Union[str, BinaryIO], series: Optional[str] = "Lookout",
             deps: Iterable = tuple(), create_missing_dirs: bool = True):
        """
        Serialize the model to a file.

        :param output: Path to the file or a file object.
        :param series: Name of the model series.
        :param deps: List of the dependencies.
        :param create_missing_dirs: create missing directories in output path if the output is a \
                                    path.
        :return: self
        """
        return super().save(output=output, series=series, deps=deps,
                            create_missing_dirs=create_missing_dirs)

    def _load_tree(self, tree: dict):
        self.ptr = ReferencePointer(*tree["ptr"])

    def _generate_tree(self) -> dict:
        return {"ptr": list(self.ptr), "name": self.name}


class DummyAnalyzerModel(AnalyzerModel):
    """
    Stub for stateless analyzers.
    """

    NAME = "dummy"
    VENDOR = "public domain"
    DESCRIPTION = "Model that does not contain anything is acts as a stub for stateless analyzers."


class Analyzer:
    """
    Interface of all the analyzers. Each analyzer uses a model to run the analysis and generates \
    a model as the result of the training.

    `version` allows to version the models. It is checked in the model repository and if it does
    not match, a new model is trained.
    `model_type` points to the specific derivative of AnalyzerModel - type of the model used
    in analyze() and generated in train().
    """

    version = None  # type: int
    model_type = None  # type: Type[AnalyzerModel]
    name = None  # type: str
    vendor = None  # type: str

    def __init__(self, model: AnalyzerModel, url: str, config: Mapping[str, Any]):
        """
        Initialize a new instance of Analyzer. A call to `analyze()` is expected after.

        :param model: The instance of the model loaded from the repository or freshly trained.
        :param url: The analyzed project's Git remote.
        :param config: Configuration of the analyzer of unspecified structure.
        """
        self._log = logging.getLogger(type(self).__name__)
        self.model = model
        self.url = url
        self.config = config

    def analyze(self, ptr_from: ReferencePointer, ptr_to: ReferencePointer,
                data_service: "lookout.core.data_requests.DataService", **data) -> List[Comment]:
        """
        Run the analysis on the specified Git repository state.

        This is called on Review events. It must return the list of `Comment`-s - found review \
        suggestions.

        :param ptr_from: The Git revision of the fork point. Exists in both the original and \
                         the forked repositories.
        :param ptr_to: The Git revision to analyze. Exists only in the forked repository.
        :param data_service: The channel to the data service in Lookout server to query for \
                             UASTs, file contents, etc.
        :param data: Extra data passed into the method. Used by the decorators to simplify \
                     the data retrieval.
        :return: List of found review suggestions. Refer to \
                 lookout/core/server/sdk/service_analyzer.proto.
        """
        raise NotImplementedError

    @classmethod
    def train(cls, ptr: ReferencePointer, config: Mapping[str, Any],
              data_service: "lookout.core.data_requests.DataService", **data) -> AnalyzerModel:
        """
        Generate a new model on top of the specified source code.

        :param ptr: Git repository state pointer.
        :param config: Configuration of the training of unspecified structure.
        :param data_service: The channel to the data service in Lookout server to query for \
                             UASTs, file contents, etc.
        :param data: Extra data passed into the method. Used by the decorators to simplify \
                     the data retrieval.
        :return: Instance of `AnalyzerModel` (`model_type`, to be precise).
        """
        raise NotImplementedError

    @classmethod
    def construct_model(cls, ptr: ReferencePointer) -> AnalyzerModel:
        """
        Produce a new empty model associated with this analyzer.

        :param ptr: state of Git repository which is used to generate the model.
        :return: Instance of the model.
        """
        return cls.model_type.generate(cls, ptr)

    @classmethod
    def check_training_required(
            cls, old_model: AnalyzerModel, ptr: ReferencePointer, config: Mapping[str, Any],
            data_service: "lookout.core.data_requests.DataService", **data) -> bool:
        """
        Decide whether we need to train the model or re-use the old one.

        :param old_model: Previously trained model. It is never None.
        :param ptr: Git repository state pointer.
        :param config: Configuration of the training of unspecified structure.
        :param data_service: The channel to the data service in Lookout server to query for \
                             UASTs, file contents, etc.
        :param data: Extra data passed into the method. Used by the decorators to simplify \
                     the data retrieval.
        :return: True (required) or False (not required)
        """
        return True
