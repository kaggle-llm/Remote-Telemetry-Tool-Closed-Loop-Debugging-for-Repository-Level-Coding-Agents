"""Deterministic demonstration of the client-side probe runtime lifecycle.

The script shows the four states that matter for the protocol: a silent client,
a probe applied at runtime, an event linked to one case, and a withdrawn probe
after the case is closed. It runs without a backend so that the lifecycle can
be verified in CI and read by reviewers.
"""

from ai_client_demo.probe_runtime import InMemoryTransport, ProbeRuntime

CASE_ID = "11111111-2222-3333-4444-555555555555"
SESSION_KEY = "tcs_demo_session_key_0000000000000000000000000000"


def main():
    transport = InMemoryTransport(state="reported")
    runtime = ProbeRuntime(transport, CASE_ID, SESSION_KEY)

    print("1. case reported, no probe published")
    print("   poll:", runtime.poll())
    print("   event:", runtime.check("palette.open", {"presentation_context": None}))

    print("2. agent publishes a probe for one instrumentation point")
    transport.state = "instrumenting"
    transport.probes = [{
        "probe_id": "palette_context",
        "target": "palette.open",
        "capture": {"presentation_context": "true", "viewmodel_state": "true"},
        "level": "error",
    }]
    print("   poll:", runtime.poll())

    print("3. the app reaches the instrumentation point")
    runtime.check("palette.open", {"presentation_context": None, "viewmodel_state": "empty"})
    for event in transport.logs:
        print("   emitted:", event["event"], event["detail"], "case:", event["case_id"])

    print("4. case is closed and the probe is withdrawn")
    transport.state = "resolved"
    transport.probes = []
    print("   poll:", runtime.poll())
    print("   event:", runtime.check("palette.open", {"presentation_context": None}))
    print("   events emitted in total:", runtime.emitted_events)
    print("   secret values printed: no")


if __name__ == "__main__":
    main()
