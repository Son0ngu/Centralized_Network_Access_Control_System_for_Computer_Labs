import os
import sys

import pytest


AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from core.agent import make_runtime
from core.lifecycle import (
    AgentComponent,
    InitResult,
    LifecycleContext,
    STATUS_FAILED,
    STATUS_OK,
    start_components,
    stop_components,
)


class FakeComponent(AgentComponent):
    def __init__(self, name, events, *, fail_on_start=False, reported_status=STATUS_OK):
        self.name = name
        self.events = events
        self.fail_on_start = fail_on_start
        self.reported_status = reported_status

    def start(self, context):
        self.events.append(f"start:{self.name}")
        if self.fail_on_start:
            raise RuntimeError(f"{self.name} failed")
        context.result.record(self.name, self.reported_status)

    def stop(self, context):
        self.events.append(f"stop:{self.name}")

    def health(self, context):
        return {"name": self.name, "status": self.reported_status}


def make_context():
    return LifecycleContext(runtime=make_runtime(), config={}, result=InitResult())


def test_start_components_preserves_order_and_stop_reverses_order():
    events = []
    context = make_context()
    components = [
        FakeComponent("registration", events),
        FakeComponent("token", events),
        FakeComponent("whitelist", events),
    ]

    start_components(context, components)
    assert events == ["start:registration", "start:token", "start:whitelist"]
    assert context.runtime.components == components

    stop_components(context)
    assert events == [
        "start:registration",
        "start:token",
        "start:whitelist",
        "stop:whitelist",
        "stop:token",
        "stop:registration",
    ]
    assert context.runtime.components == []


def test_start_exception_cleans_up_started_and_starting_components():
    events = []
    context = make_context()
    components = [
        FakeComponent("registration", events),
        FakeComponent("token", events, fail_on_start=True),
        FakeComponent("whitelist", events),
    ]

    with pytest.raises(RuntimeError, match="token failed"):
        start_components(context, components)

    assert events == [
        "start:registration",
        "start:token",
        "stop:token",
        "stop:registration",
    ]
    assert context.runtime.components == []
    failed = [c for c in context.result.components if c.status == STATUS_FAILED]
    assert failed
    assert failed[-1].name == "token"


def test_reported_failed_status_cleans_up_including_reporting_component():
    events = []
    context = make_context()
    components = [
        FakeComponent("registration", events),
        FakeComponent("firewall", events, reported_status=STATUS_FAILED),
        FakeComponent("log_sender", events),
    ]

    with pytest.raises(RuntimeError, match="firewall"):
        start_components(context, components)

    assert events == [
        "start:registration",
        "start:firewall",
        "stop:firewall",
        "stop:registration",
    ]
    assert context.runtime.components == []
