import numpy
from collections import OrderedDict
from sortedcontainers import SortedDict
from typing import Tuple, Dict, Iterator, Sequence, List, Iterable, Union, Optional

from lookout.sdk.service_data_pb2 import File

from lookout.core.annotations.annotation import Annotation, LineAnnotation, PathAnnotation, \
    UASTNodeAnnotation, LanguageAnnotation, ValuedAnnotation


class Annotations(OrderedDict):
    """
    Annotations collection for a specific range
    """

    def __init__(self, start, stop, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._range = (start, stop)
        self._start = start
        self._stop = stop

    def __getattr__(self, item):
        if item in self:
            annotation = self[item]
            if isinstance(annotation, ValuedAnnotation):
                return self[item].value
            else:
                return None
        else:
            raise AttributeError("Attribute %s does not exist" % item)

    start = property(lambda self: self._start)

    stop = property(lambda self: self._stop)

    range = property(lambda self: self._range)


class RawData:
    """The storage for ordered document collection indexed and accessible by global offsets."""

    def __init__(self, document_collection: Iterable[bytes]):
        assert len(document_collection) > 0
        self._document_collection = list(document_collection)

        doc_lens = [0] + [len(d) for d in self._document_collection[:-1]]
        self._doc_start_offset = numpy.array(doc_lens).cumsum()

    def _offset_to_doc_index(self, offset: int) -> Tuple[int, int]:
        doc_index = numpy.argmax(self._doc_start_offset > offset) - 1
        return doc_index, offset - self._doc_start_offset[doc_index]

    def __getitem__(self, index: Union[slice, int, tuple]) -> bytes:
        """
        main function to access data pieces by offset.
        :param index:
        :return:
        """
        if isinstance(index, int):
            doc_index, doc_offset = self._offset_to_doc_index(index)
            return self._document_collection[doc_index][doc_offset]
        elif isinstance(index, slice):
            if isinstance(index, slice) and index.step is not None:
                raise IndexError("Step in unsupported for slices.")
            return self._get_range(index.start, index.stop)
        elif isinstance(index, tuple):
            assert len(index) == 2
            return self._get_range(*index)
        else:
            raise IndexError("Unknown index type %s" % type(index))

    def _get_range(self, start: int, stop: int) -> bytes:
        doc_index_start, doc_offset_start = self._offset_to_doc_index(start)
        doc_index_end, doc_offset_end = self._offset_to_doc_index(stop - 1)
        if doc_index_start != doc_index_end:
            raise IndexError("You can get data only from one document from collection")
        return self._document_collection[doc_index_start][doc_offset_start: doc_offset_end + 1]

    def get_docs_range(self):
        return tuple(zip(self._doc_start_offset, self._doc_start_offset[1:]))


class AnnotatedData:
    """
    Class that couples annotations and data together.

    All special utilities to work with annotations should be implemented in this class
    List of methods that should be implemented can be found here:
    https://uima.apache.org/d/uimafit-current/api/org/apache/uima/fit/util/JCasUtil.html
    """
    def __init__(self, raw_data: RawData):
        self._raw_data = raw_data
        # Interval trees should be used for _range_to_annotations later.
        self._range_to_annotations = SortedDict()  # type: OrderedDict[(int, int), Dict[str, Annotation]]  # noqa E501
        self._type_to_annotations = {}  # type: Dict[str, OrderedDict[(int, int), Annotation]]

    def __getitem__(self, item):
        return self._raw_data[item]

    def add(self, annotation: Annotation) -> None:
        """
        Add annotation.
        """
        if annotation.range not in self._range_to_annotations:
            self._range_to_annotations[annotation.range] = {}
        if annotation.name not in self._type_to_annotations:
            self._type_to_annotations[annotation.name] = SortedDict()
        self._range_to_annotations[annotation.range][annotation.name] = annotation
        self._type_to_annotations[annotation.name][annotation.range] = annotation

    def extend(self, annotations: Iterable[Annotation]) -> None:
        """
        Extend with annotations.
        """
        for annotation in annotations:
            self._range_to_annotations[annotation.range][annotation.name] = annotation
            self._type_to_annotations[annotation.name][annotation.range] = annotation

    def get(self, position: Tuple[int, int]) -> Tuple[bytes, Dict[str, Annotation]]:
        """
        Get annotated value and all annotations for the range.
        """
        raise NotImplementedError()

    def get_value(self, position: Tuple[int, int]) -> Tuple[bytes, Dict[str, Annotation]]:
        """
        Get annotated value and all annotations for the range.
        """
        raise NotImplementedError()

    def iter_annotation(self, name: str, start_offset: Optional[int] = None,
                        stop_offset: Optional[int] = None) -> Iterator[Tuple[bytes, Annotation]]:
        """
        Iter through specific annotation atomic_tokens, ys, files, etc
        returns slice of RawData and its annotation.
        """
        if start_offset is not None or stop_offset is not None:
            raise NotImplementedError()

        for range, value in self._type_to_annotations[name].items():
            yield self[range], value

    def iter_annotations(self, names: Sequence[str], start_offset: Optional[int] = None,
                         stop_offset: Optional[int] = None
                         ) -> Iterator[Tuple[bytes, Annotations]]:
        """
        Iter through specific annotations.
        returns slice of RawData and its annotation.
        """
        if start_offset is not None or stop_offset is not None:
            raise NotImplementedError()

        names_set = frozenset(names)
        for value, annotation0 in self.iter_annotation(names[0]):
            all_annotations = self._range_to_annotations[annotation0.range]
            if names_set <= all_annotations.keys():
                yield value, Annotations(*annotation0.range, (
                    (key, all_annotations[key]) for key in names))

    def subiter_annotation(self, name: str, covering_annotation: Annotation):
        raise NotImplementedError()

    def sub_iter_annotations(self, names: Sequence[str], covering_annotation: Annotation):
        raise NotImplementedError()

    @classmethod
    def from_files(cls, files: Iterable[File]) -> "AnnotatedData":
        """
        Create AnnotatedData instance from files.

        :param files:
        :return: new AnnotatedData instance
        """
        raw_data = RawData(file.content for file in files)
        file_ranges = raw_data.get_docs_range()
        annotated_data = AnnotatedData(raw_data)
        for file_range, file in zip(file_ranges, files):
            annotated_data.add(PathAnnotation(*file_range, file.path))
            annotated_data.add(UASTNodeAnnotation(*file_range, file.uast))
            annotated_data.add(LanguageAnnotation(*file_range, file.language))
        return annotated_data
