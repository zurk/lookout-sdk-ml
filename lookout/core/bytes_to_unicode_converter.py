from typing import Dict, Iterator

import bblfsh
from lookout.sdk.service_data_pb2 import Change, File
import numpy

from lookout.core.analyzer import UnicodeChange, UnicodeFile


class BytesToUnicodeConverter:
    """Utility class to convert bytes positions to unicode positions in `bblfsh.Node`."""

    def __init__(self, content: bytes):
        """
        Initialize a new instance of BytesToUnicodeConverter.

        :param content: Code byte representation.
        """
        self._content = content
        self._content_str = content.decode(errors="replace")
        self._lines = self._content_str.splitlines(keepends=True)
        self._byte_to_str_offset = self._build_bytes_to_str_offset_mapping(content)
        self._lines_offset = self._build_lines_offset_mapping(self._content_str)

    def convert_content(self):
        """Convert byte content (or code) to unicode."""
        return self._content_str

    def convert_uast(self, uast: bblfsh.Node) -> bblfsh.Node:
        """
        Convert uast Nodes bytes position to unicode position.

        UAST is expected to correspond to provided content.
        :param uast: corresponding UAST.
        :return: UAST with unicode positions.
        """
        uast = bblfsh.Node.FromString(uast.SerializeToString())  # deep copy the whole tree
        if not self._content:
            return uast
        for node in self._traverse_uast(uast):
            for position in (node.start_position, node.end_position):
                if position.offset == 0 and position.col == 0 and position.line == 0:
                    continue
                new_position = self._get_position(self._byte_to_str_offset[position.offset])
                for attr in ("offset", "line", "col"):
                    setattr(position, attr, getattr(new_position, attr))
        return uast

    def _get_position(self, offset: int) -> bblfsh.Position:
        """Get new position for unicode string offset."""
        line_num = numpy.argmax(self._lines_offset > offset) - 1
        col = offset - self._lines_offset[line_num]
        line = self._lines[line_num]
        if len(line) == col:
            if line.splitlines()[0] != line:
                # ends with newline
                line_num += 1
                col = 0
        return bblfsh.Position(offset=offset, line=line_num + 1, col=col + 1)

    @staticmethod
    def _build_lines_offset_mapping(content: str) -> numpy.ndarray:
        if not content:
            return numpy.empty(shape=(0, 0))
        line_start_offsets = [0]
        for d in content.splitlines(keepends=True):
            line_start_offsets.append(line_start_offsets[-1] + len(d))
        line_start_offsets[-1] += 1
        return numpy.array(line_start_offsets)

    @staticmethod
    def _build_bytes_to_str_offset_mapping(content: bytes) -> Dict[int, int]:
        """
        Create a dictionary with bytes offset to unicode string offset mapping.

        :param content: Bytes object which is used to create offsets mapping.
        :return: Dictionary with bytes offset to unicode string offset mapping.
        """
        byte_to_str_offset = {0: 0}
        byte_len_before = 0
        content_str = content.decode(errors="replace")
        for i, char in enumerate(content_str):
            if char != "\ufffd":  # replacement character
                byte_len_before += len(char.encode())
            else:
                byte_len_before += 1
            byte_to_str_offset[byte_len_before] = i + 1
        byte_to_str_offset[len(content)] = len(content_str)
        return byte_to_str_offset

    @staticmethod
    def _traverse_uast(uast: "bblfsh.Node") -> Iterator["bblfsh.Node"]:
        stack = [uast]
        while stack:
            node = stack.pop(0)
            stack.extend(node.children)
            yield node

    @staticmethod
    def convert_file(file: File) -> UnicodeFile:
        """
        Convert lookout `File` to `UnicodeFile` with converted content and uast.

        path and language fields are the same for result and provided `File` instance.

        :param file: lookout File to convert.
        :return: New UnicodeFile instance.
        """
        converter = BytesToUnicodeConverter(file.content)
        return UnicodeFile(
            content=converter.convert_content(),
            uast=converter.convert_uast(file.uast),
            path=file.path,
            language=file.language,
        )

    @staticmethod
    def convert_change(change: Change) -> UnicodeChange:
        """
        Convert lookout `Change` to `UnicodeChange` with converted content and uast.

        :param change: lookout Change to convert.
        :return: New UnicodeChange instance.
        """
        return Change(
            base=BytesToUnicodeConverter.convert_file(change.base),
            head=BytesToUnicodeConverter.convert_file(change.head),
        )
