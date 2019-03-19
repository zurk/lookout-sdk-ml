import os
from pathlib import Path
import threading
import unittest

import bblfsh

import lookout.core
from lookout.core.analyzer import ReferencePointer, UnicodeFile
from lookout.core.api.event_pb2 import PushEvent, ReviewEvent
from lookout.core.api.service_analyzer_pb2 import EventResponse
from lookout.core.data_requests import (
    DataService, parse_uast, UnicodeDataService, with_changed_contents, with_changed_uasts,
    with_changed_uasts_and_contents, with_contents, with_uasts, with_uasts_and_contents,
    with_unicode_data_service)
from lookout.core.event_listener import EventHandlers, EventListener
from lookout.core.helpers.server import find_port, LookoutSDK
import lookout.core.tests
from lookout.core.tests.test_bytes_to_unicode_converter import check_uast_transformation


class DataRequestsTests(unittest.TestCase, EventHandlers):
    COMMIT_FROM = "3ac2a59275902f7252404d26680e30cc41efb837"
    COMMIT_TO = "dce7fcba3d2151a0d5dc4b3a89cfc0911c96cf2b"

    def setUp(self):
        self.setUpEvent = threading.Event()
        self.tearDownEvent = threading.Event()
        self.port = find_port()
        self.lookout_sdk = LookoutSDK()
        self.listener = EventListener("localhost:%d" % self.port, self).start()
        self.server_thread = threading.Thread(target=self.run_data_service)
        self.server_thread.start()
        self.data_service = DataService("localhost:10301")
        self.url = "file://" + str(Path(lookout.core.__file__).parent.parent.absolute())
        self.ref = "refs/heads/master"
        self.setUpWasSuccessful = True
        self.setUpEvent.wait()
        if not self.setUpWasSuccessful:
            self.fail("failed to setUp()")

    def tearDown(self):
        self.data_service.shutdown()
        self.tearDownEvent.set()
        self.listener.stop()
        self.server_thread.join()

    def process_review_event(self, request: ReviewEvent) -> EventResponse:
        self.setUpEvent.set()
        self.tearDownEvent.wait()
        return EventResponse()

    def process_push_event(self, request: PushEvent) -> EventResponse:
        self.setUpEvent.set()
        self.tearDownEvent.wait()
        return EventResponse()

    def run_data_service(self):
        try:
            self.lookout_sdk.push(self.COMMIT_FROM, self.COMMIT_TO, self.port,
                                  git_dir=os.getenv("LOOKOUT_SDK_ML_TESTS_GIT_DIR", "."))
        except Exception as e:
            print(type(e).__name__, e)
            self.setUpWasSuccessful = False
            self.setUpEvent.set()

    def test_with_changed_uasts(self):
        def func(imposter, ptr_from: ReferencePointer, ptr_to: ReferencePointer,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            changes = list(data["changes"])
            self.assertEqual(len(changes), 1)
            change = changes[0]
            self.assertEqual(change.base.content, b"")
            self.assertEqual(change.head.content, b"")
            self.assertEqual(type(change.base.uast).__module__, bblfsh.Node.__module__)
            self.assertEqual(type(change.head.uast).__module__, bblfsh.Node.__module__)
            self.assertEqual(change.base.path, change.head.path)
            self.assertEqual(change.base.path, "lookout/core/manager.py")
            self.assertEqual(change.base.language, "Python")
            self.assertEqual(change.head.language, "Python")

        func = with_changed_uasts(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_FROM),
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             self.data_service)

    def test_with_changed_contents(self):
        def func(imposter, ptr_from: ReferencePointer, ptr_to: ReferencePointer,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            changes = list(data["changes"])
            self.assertEqual(len(changes), 1)
            change = changes[0]
            self.assertEqual(len(change.base.content), 5548)
            self.assertEqual(len(change.head.content), 5542)
            self.assertFalse(change.base.uast.children)
            self.assertFalse(change.head.uast.children)
            self.assertEqual(change.base.path, change.head.path)
            self.assertEqual(change.base.path, "lookout/core/manager.py")
            self.assertEqual(change.base.language, "Python")
            self.assertEqual(change.head.language, "Python")

        func = with_changed_contents(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_FROM),
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             self.data_service)

    def test_with_changed_uasts_and_contents(self):
        def func(imposter, ptr_from: ReferencePointer, ptr_to: ReferencePointer,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            changes = list(data["changes"])
            self.assertEqual(len(changes), 1)
            change = changes[0]
            self.assertEqual(len(change.base.content), 5548)
            self.assertEqual(len(change.head.content), 5542)
            self.assertEqual(type(change.base.uast).__module__, bblfsh.Node.__module__)
            self.assertEqual(type(change.head.uast).__module__, bblfsh.Node.__module__)
            self.assertEqual(change.base.path, change.head.path)
            self.assertEqual(change.base.path, "lookout/core/manager.py")
            self.assertEqual(change.base.language, "Python")
            self.assertEqual(change.head.language, "Python")

        func = with_changed_uasts_and_contents(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_FROM),
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             self.data_service)

    def test_with_uasts(self):
        def func(imposter, ptr: ReferencePointer, config: dict,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            files = list(data["files"])
            self.assertEqual(len(files), 18)
            for file in files:
                self.assertEqual(file.content, b"")
                self.assertEqual(type(file.uast).__module__, bblfsh.Node.__module__)
                self.assertTrue(file.path)
                self.assertIn(file.language, ("Python", "YAML", "Dockerfile", "Markdown",
                                              "Jupyter Notebook", "Shell", "Text", ""))

        func = with_uasts(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             None,
             self.data_service)

    def test_with_contents(self):
        def func(imposter, ptr: ReferencePointer, config: dict,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            files = list(data["files"])
            self.assertEqual(len(files), 18)
            non_empty_langs = 0
            for file in files:
                if not file.path.endswith("__init__.py"):
                    self.assertGreater(len(file.content), 0, file.path)
                self.assertFalse(file.uast.children)
                self.assertTrue(file.path)
                if file.language:
                    non_empty_langs += 1
                self.assertIn(file.language, ("Python", "YAML", "Dockerfile", "Markdown",
                                              "Jupyter Notebook", "Shell", "Text", ""))
            self.assertGreater(non_empty_langs, 0)

        func = with_contents(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             None,
             self.data_service)

    def test_with_uasts_and_contents(self):
        def func(imposter, ptr: ReferencePointer, config: dict,
                 data_service: DataService, **data):
            self.assertIsInstance(data_service, DataService)
            files = list(data["files"])
            self.assertEqual(len(files), 18)
            for file in files:
                if not file.path.endswith("__init__.py"):
                    self.assertGreater(len(file.content), 0, file.path)
                self.assertEqual(type(file.uast).__module__, bblfsh.Node.__module__)
                self.assertTrue(file.path)
                self.assertIn(file.language, ("Python", "YAML", "Dockerfile", "Markdown",
                                              "Jupyter Notebook", "Shell", "Text", ""))

        func = with_uasts_and_contents(func)
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             None,
             self.data_service)

    def test_with_unicode_data_service(self):
        def func(imposter, ptr: ReferencePointer, config: dict,
                 data_service: UnicodeDataService, **data):
            self.assertIsInstance(data_service, UnicodeDataService)
            files = list(data["files"])
            self.assertEqual(len(files), 18)
            for file in files:
                self.assertIsInstance(file, UnicodeFile)
                self.assertIsInstance(file.content, str)
                if not file.path.endswith("__init__.py"):
                    self.assertGreater(len(file.content), 0, file.path)
                self.assertEqual(type(file.uast).__module__, bblfsh.Node.__module__)
                self.assertTrue(file.path)
                self.assertIn(file.language, ("Python", "YAML", "Dockerfile", "Markdown",
                                              "Jupyter Notebook", "Shell", "Text", ""))

        func = with_unicode_data_service(with_uasts_and_contents(func))
        func(self,
             ReferencePointer(self.url, self.ref, self.COMMIT_TO),
             None,
             self.data_service)

    def test_babelfish(self):
        uast, errors = parse_uast(self.data_service.get_bblfsh(), "console.log('hi');", "hi.js")
        self.assertIsInstance(uast, bblfsh.Node)
        self.assertEqual(len(errors), 0, str(errors))

    def test_babelfish_with_unicode(self):
        content = b"console.log('\xc3\x80');"
        data_service_uni = UnicodeDataService.from_data_service(self.data_service)
        request = bblfsh.aliases.ParseRequest(filename="hi.js",
                                              content=content.decode(),
                                              language=None)
        try:
            response_uni = data_service_uni.get_bblfsh().Parse(request)
            response_bytes = self.data_service.get_bblfsh().Parse(request)
            self.assertIsInstance(response_uni.uast, bblfsh.Node)
            self.assertIsInstance(response_bytes.uast, bblfsh.Node)
            self.assertEqual(len(response_uni.errors), 0, str(response_uni.errors))
            self.assertEqual(len(response_bytes.errors), 0, str(response_bytes.errors))
            check_uast_transformation(self, content, response_bytes.uast, response_uni.uast)
        finally:
            data_service_uni.shutdown()


if __name__ == "__main__":
    unittest.main()
