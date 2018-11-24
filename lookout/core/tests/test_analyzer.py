import unittest

from lookout.core.analyzer import Analyzer, DummyAnalyzerModel, ReferencePointer


class FakeAnalyzer(Analyzer):
    version = 7
    model_type = DummyAnalyzerModel
    name = "fake"


class AnalyzerTests(unittest.TestCase):
    def test_dummy_model(self):
        ptr = ReferencePointer("1", "2", "3")
        model = DummyAnalyzerModel().construct(FakeAnalyzer, ptr)
        self.assertEqual(model.name, FakeAnalyzer.name)
        self.assertEqual(model.version, [FakeAnalyzer.version])
        self.assertEqual(model.ptr, ptr)


if __name__ == "__main__":
    unittest.main()
