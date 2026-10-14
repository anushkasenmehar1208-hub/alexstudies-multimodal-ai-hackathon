"""Regression coverage for build-time Track D route registration."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from uni_app.knowledge_base.api import register_knowledge_base_routes


class _RouteCollector:
    def __init__(self) -> None:
        self.routes: list[str] = []

    def add_route(self, path, endpoint, methods=None) -> None:
        del endpoint, methods
        self.routes.append(path)


class TrackDLazyInitializationTests(unittest.TestCase):
    def test_routes_register_without_database_url_during_build(self) -> None:
        app = _RouteCollector()
        environment = os.environ.copy()
        environment.pop("DATABASE_URL", None)

        with mock.patch.dict(os.environ, environment, clear=True):
            service = register_knowledge_base_routes(
                app,
                auth_resolver=lambda token: 1,
            )

            self.assertEqual(len(app.routes), 12)
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required"):
                _ = service.engine


if __name__ == "__main__":
    unittest.main()
