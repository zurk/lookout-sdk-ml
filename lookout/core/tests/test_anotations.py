import io
import unittest

from lookout.core.annotations.annotated_data import RawData, AnnotatedData
from lookout.core.annotations.annotation import PathAnnotation, UASTNodeAnnotation, TokenAnnotation


class AnnotationsTests(unittest.TestCase):
    def test_raw_data(self):
        collection = [
            b"01234567",
            b"890123456789",
            b"123456787655",
        ]
        raw_data = RawData(collection)
        self.assertEqual(raw_data[0:2], b"01")
        self.assertEqual(collection[1],
            raw_data[len(collection[0]):
                     len(collection[0])+len(collection[1])])
        self.assertEqual(collection[2],
                         raw_data[(len(collection[0]) + len(collection[1]),
                                   len(collection[0]) + len(collection[1]) + len(collection[2]))])
        with self.assertRaises(IndexError):
            raw_data[len(collection[0]):len(collection[0]) + len(collection[1]) + 1]
        with self.assertRaises(IndexError):
            raw_data["asd"]

    def test_annotations(self):
        collection = [
            b"01234567",
            b"890123456789",
            b"123456787655",
        ]
        lens = [len(c) for c in collection]
        raw_data = RawData(collection)
        annotated_data = AnnotatedData(raw_data)
        annotated_data.add(TokenAnnotation(0, 3))
        annotated_data.add(TokenAnnotation(3, 3))
        annotated_data.add(TokenAnnotation(3, 4))
        annotated_data.add(PathAnnotation(0, lens[0], "1"))
        annotated_data.add(PathAnnotation(lens[0],
                                          lens[0] + lens[1], "2"))
        annotated_data.add(PathAnnotation(lens[0] + lens[1],
                                          lens[0] + lens[1] + lens[2], "3"))

        for annotations in annotated_data.iter_annotations(["token", "path"]):
            print(annotations)


if __name__ == "__main__":
    unittest.main()
