# Native generation response capture

The generation boundary captures the provider HTTP response body before JSON
decoding, usage extraction or answer parsing. The existing structured success
answer remains separate. A rejected output stays rejected and stops the native
batch; diagnostics do not grant permission to approve, repair or retry it.

Payloads live under `workspace/generation-response-captures/<run>/<question>/`,
inside the project but Git-ignored, with owner-only directories and files. Exact
body bytes are published through a durable hash-bound receipt. The source-free
`RAW_RESPONSE_CAPTURE.json` sidecar is sealed into the normal question/run
manifest. It binds the run, question, request, M8 package, mode and body hash.
No credentials, request headers or publisher output enter ordinary terminal logs.
Authentication-error bodies are withheld because they may echo credentials.

Capture status is independently reported as `RAW_RESPONSE_CAPTURED`,
`RAW_RESPONSE_CAPTURE_FAILED` or `RAW_RESPONSE_UNAVAILABLE`. Saving failure stops
further paid execution, retains available usage, and never claims a usable body
reference. A timeout may have no provider body. Neither condition authorizes a
retry or release of spending reservations. Crash/storage failures can leave an
unpublished private partial file; only verified sealed references are viewable.

Generation rejection retains the existing top-level status and adds specific
codes/field paths for malformed JSON, duplicate keys, schema/relationship errors,
unauthorized evidence, model mismatch, refusal and incomplete responses. Error
input values and Pydantic context are excluded to avoid copying source passages.

The canonical Streamlit dashboard remains on port **8514**. Human Review includes
a separate, read-only **response failure diagnostics** view. Select the failed
question and explicitly select **Show protected raw provider response** on
localhost. Raw text is displayed as escaped code, never rendered as instructions
or HTML. No approval, retry or generation controls are provided for diagnostic
items. Existing normal answer review and signed/local POC decisions are unchanged.
Historical Q12/Q18 failures appear with raw output explicitly unavailable; this
change cannot reconstruct output that was never retained.

Capture adds local persistence only. The prompt v2.2, response schema 2.0,
outbound request, model, output reserve, evidence budget, pricing and strict
validation are unchanged. API latency excludes capture writes; adapter/question
elapsed time includes local work. No extra provider request is made to capture.

Implementation changes require reviewed successor trust bindings and exact
historical code snapshots. Historical manifests and prior authorizations are
never rewritten. A new trust baseline does not renew an authorization or unlock
admitted IDs. Q19/Q20 remain locked after the partial Batch04; continuation needs
separate owner review. No Q12/Q18 retry or Batch05–07 execution is authorized.
