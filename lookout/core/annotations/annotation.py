from typing import Any


class Annotation:
    """Base class for annotation"""

    name = None  # Should be defined in inheritors

    def __init__(self, start: int, stop: int):
        if self.name is None:
            raise NotImplementedError("name should be defined for Annotation.")
        self._range = (start, stop)
        self._start = start
        self._stop = stop

    start = property(lambda self: self._start)

    stop = property(lambda self: self._stop)

    range = property(lambda self: self._range)


class ValuedAnnotation(Annotation):
    def __init__(self, start: int, stop: int, value: Any):
        super().__init__(start, stop)
        self.value = value


# Specific annotations for style-analyzer:
class AnnotationNames:
    atomic_token = "atomic_token"
    token = "token"
    line = "line"
    uast_node = "uast_node"
    language = "language"
    path = "path"


class TokenAnnotation(Annotation):
    """Virtual сode token annotation"""

    name = AnnotationNames.token


class AtomicTokenAnnotation(Annotation):
    """Infrangible сode token annotation"""

    name = AnnotationNames.atomic_token


class LineAnnotation(ValuedAnnotation):
    """Line number annotation"""

    name = AnnotationNames.line


class UASTNodeAnnotation(ValuedAnnotation):
    """UAST Node annotation"""

    name = AnnotationNames.uast_node

    @staticmethod
    def from_node(node: "bblfsh.Node") -> "UASTNodeAnnotation":
        return UASTNodeAnnotation(node.start_position.offset, node.end_position.offset, node)


class LanguageAnnotation(ValuedAnnotation):
    """File language annotation"""

    name = AnnotationNames.language


class PathAnnotation(ValuedAnnotation):
    """File language annotation"""

    name = AnnotationNames.path
