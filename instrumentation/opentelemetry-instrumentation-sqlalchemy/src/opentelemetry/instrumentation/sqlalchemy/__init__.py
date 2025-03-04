# Copyright The OpenTelemetry Authors
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

"""
Instrument `sqlalchemy`_ to report SQL queries.

There are two options for instrumenting code. The first option is to use
the ``opentelemetry-instrument`` executable which will automatically
instrument your SQLAlchemy engine. The second is to programmatically enable
instrumentation via the following code:

.. _sqlalchemy: https://pypi.org/project/sqlalchemy/

SQLCOMMENTER
****************************************
You can optionally configure SQLAlchemy instrumentation to enable sqlcommenter which enriches
the query with contextual information.

Usage
-----

.. code:: python

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(enable_commenter=True, commenter_options={})


For example,
::

    Invoking engine.execute("select * from auth_users") will lead to sql query "select * from auth_users" but when SQLCommenter is enabled
    the query will get appended with some configurable tags like "select * from auth_users /*tag=value*/;"

SQLCommenter Configurations
***************************
We can configure the tags to be appended to the sqlquery log by adding configuration inside commenter_options(default:{}) keyword

db_driver = True(Default) or False

For example,
::
Enabling this flag will add any underlying driver like psycopg2 /*db_driver='psycopg2'*/

db_framework = True(Default) or False

For example,
::
Enabling this flag will add db_framework and it's version /*db_framework='sqlalchemy:0.41b0'*/

opentelemetry_values = True(Default) or False

For example,
::
Enabling this flag will add traceparent values /*traceparent='00-03afa25236b8cd948fa853d67038ac79-405ff022e8247c46-01'*/

Usage
-----
.. code:: python

    from sqlalchemy import create_engine

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    import sqlalchemy

    engine = create_engine("sqlite:///:memory:")
    SQLAlchemyInstrumentor().instrument(
        engine=engine,
    )

    # of the async variant of SQLAlchemy

    from sqlalchemy.ext.asyncio import create_async_engine

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    import sqlalchemy

    engine = create_async_engine("sqlite:///:memory:")
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine
    )

API
---
"""
from collections.abc import Sequence
from typing import Collection

import sqlalchemy
from packaging.version import parse as parse_version
from sqlalchemy.engine.base import Engine
from wrapt import wrap_function_wrapper as _w

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.sqlalchemy.engine import (
    EngineTracer,
    _get_tracer,
    _wrap_connect,
    _wrap_create_async_engine,
    _wrap_create_engine,
)
from opentelemetry.instrumentation.sqlalchemy.package import _instruments
from opentelemetry.instrumentation.utils import unwrap


class SQLAlchemyInstrumentor(BaseInstrumentor):
    """An instrumentor for SQLAlchemy
    See `BaseInstrumentor`
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Instruments SQLAlchemy engine creation methods and the engine
        if passed as an argument.

        Args:
            **kwargs: Optional arguments
                ``engine``: a SQLAlchemy engine instance
                ``engines``: a list of SQLAlchemy engine instances
                ``tracer_provider``: a TracerProvider, defaults to global

        Returns:
            An instrumented engine if passed in as an argument or list of instrumented engines, None otherwise.
        """
        tracer_provider = kwargs.get("tracer_provider")
        _w("sqlalchemy", "create_engine", _wrap_create_engine(tracer_provider))
        _w(
            "sqlalchemy.engine",
            "create_engine",
            _wrap_create_engine(tracer_provider),
        )
        _w(
            "sqlalchemy.engine.base",
            "Engine.connect",
            _wrap_connect(tracer_provider),
        )
        if parse_version(sqlalchemy.__version__).release >= (1, 4):
            _w(
                "sqlalchemy.ext.asyncio",
                "create_async_engine",
                _wrap_create_async_engine(tracer_provider),
            )
        if kwargs.get("engine") is not None:
            return EngineTracer(
                _get_tracer(tracer_provider),
                kwargs.get("engine"),
                kwargs.get("enable_commenter", False),
                kwargs.get("commenter_options", {}),
            )
        if kwargs.get("engines") is not None and isinstance(
            kwargs.get("engines"), Sequence
        ):
            return [
                EngineTracer(
                    _get_tracer(tracer_provider),
                    engine,
                    kwargs.get("enable_commenter", False),
                    kwargs.get("commenter_options", {}),
                )
                for engine in kwargs.get("engines")
            ]

        return None

    def _uninstrument(self, **kwargs):
        unwrap(sqlalchemy, "create_engine")
        unwrap(sqlalchemy.engine, "create_engine")
        unwrap(Engine, "connect")
        if parse_version(sqlalchemy.__version__).release >= (1, 4):
            unwrap(sqlalchemy.ext.asyncio, "create_async_engine")
