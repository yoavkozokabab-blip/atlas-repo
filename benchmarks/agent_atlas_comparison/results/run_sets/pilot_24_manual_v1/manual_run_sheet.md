# Manual Benchmark Run Sheet

These are pending run cards. They become valid benchmark data only after a fresh agent
session is used and the full response/telemetry is captured with `scripts/capture_run.py`.

## 1. task_001_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_001`
- Repository: `controlled_atlas_reference` @ `218f14b90cdc23cb57e4aeccfcf247e999186f77`
- Category: `retrieval`
- Difficulty: `easy`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In repository controlled_atlas_reference, where is authentication implemented and where is it mounted into request handling? Cite the files and functions that matter. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_001_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_001 --agent cursor --no-atlas
```

## 2. task_001_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_001`
- Repository: `controlled_atlas_reference` @ `218f14b90cdc23cb57e4aeccfcf247e999186f77`
- Category: `retrieval`
- Difficulty: `easy`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In repository controlled_atlas_reference, where is authentication implemented and where is it mounted into request handling? Cite the files and functions that matter. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_001_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_001 --agent codex --atlas-enabled
```

## 3. task_001_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_001`
- Repository: `controlled_atlas_reference` @ `218f14b90cdc23cb57e4aeccfcf247e999186f77`
- Category: `retrieval`
- Difficulty: `easy`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In repository controlled_atlas_reference, where is authentication implemented and where is it mounted into request handling? Cite the files and functions that matter. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_001_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_001 --agent cursor --atlas-enabled
```

## 4. task_001_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_001`
- Repository: `controlled_atlas_reference` @ `218f14b90cdc23cb57e4aeccfcf247e999186f77`
- Category: `retrieval`
- Difficulty: `easy`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In repository controlled_atlas_reference, where is authentication implemented and where is it mounted into request handling? Cite the files and functions that matter. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_001_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_001 --agent codex --no-atlas
```

## 5. task_002_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_002`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `cross_file_reasoning`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In Requests, where is HTTP retry behavior configured for the default transport adapter, and how does a Session reach that adapter for a request? Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_002_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_002 --agent codex --atlas-enabled
```

## 6. task_002_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_002`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `cross_file_reasoning`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In Requests, where is HTTP retry behavior configured for the default transport adapter, and how does a Session reach that adapter for a request? Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_002_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_002 --agent cursor --no-atlas
```

## 7. task_002_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_002`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `cross_file_reasoning`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In Requests, where is HTTP retry behavior configured for the default transport adapter, and how does a Session reach that adapter for a request? Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_002_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_002 --agent codex --no-atlas
```

## 8. task_002_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_002`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `cross_file_reasoning`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In Requests, where is HTTP retry behavior configured for the default transport adapter, and how does a Session reach that adapter for a request? Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_002_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_002 --agent cursor --atlas-enabled
```

## 9. task_003_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_003`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `architecture`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In FastAPI, explain the request validation and dependency-resolution lifecycle from route registration to calling an endpoint for an HTTP request. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_003_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_003 --agent cursor --atlas-enabled
```

## 10. task_003_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_003`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `architecture`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In FastAPI, explain the request validation and dependency-resolution lifecycle from route registration to calling an endpoint for an HTTP request. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_003_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_003 --agent codex --no-atlas
```

## 11. task_003_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_003`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `architecture`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In FastAPI, explain the request validation and dependency-resolution lifecycle from route registration to calling an endpoint for an HTTP request. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_003_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_003 --agent codex --atlas-enabled
```

## 12. task_003_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_003`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `architecture`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In FastAPI, explain the request validation and dependency-resolution lifecycle from route registration to calling an endpoint for an HTTP request. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_003_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_003 --agent cursor --no-atlas
```

## 13. task_004_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_004`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `impact`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In FastAPI, what is likely to break if dependency_overrides_provider stops being passed into dependency solving for routes? Cite files/tests and downstream behavior. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_004_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_004 --agent codex --no-atlas
```

## 14. task_004_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_004`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `impact`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In FastAPI, what is likely to break if dependency_overrides_provider stops being passed into dependency solving for routes? Cite files/tests and downstream behavior. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_004_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_004 --agent cursor --atlas-enabled
```

## 15. task_004_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_004`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `impact`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In FastAPI, what is likely to break if dependency_overrides_provider stops being passed into dependency solving for routes? Cite files/tests and downstream behavior. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_004_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_004 --agent cursor --no-atlas
```

## 16. task_004_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_004`
- Repository: `fastapi` @ `7cb06f360dd44efac059848df1a9beee7643b018`
- Category: `impact`
- Difficulty: `hard`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In FastAPI, what is likely to break if dependency_overrides_provider stops being passed into dependency solving for routes? Cite files/tests and downstream behavior. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_004_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_004 --agent codex --atlas-enabled
```

## 17. task_005_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_005`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `debugging`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
A user reports `requests.exceptions.InvalidSchema: No connection adapters were found for 'ftp://example.com'` when calling `requests.get(...)`. Identify the likely root cause, the relevant code path, and the first files to inspect. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_005_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_005 --agent cursor --no-atlas
```

## 18. task_005_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_005`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `debugging`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
A user reports `requests.exceptions.InvalidSchema: No connection adapters were found for 'ftp://example.com'` when calling `requests.get(...)`. Identify the likely root cause, the relevant code path, and the first files to inspect. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_005_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_005 --agent cursor --atlas-enabled
```

## 19. task_005_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_005`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `debugging`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
A user reports `requests.exceptions.InvalidSchema: No connection adapters were found for 'ftp://example.com'` when calling `requests.get(...)`. Identify the likely root cause, the relevant code path, and the first files to inspect. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_005_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_005 --agent codex --atlas-enabled
```

## 20. task_005_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_005`
- Repository: `requests` @ `f361ead047be5cb873174218582f7d8b9fcd9f49`
- Category: `debugging`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
A user reports `requests.exceptions.InvalidSchema: No connection adapters were found for 'ftp://example.com'` when calling `requests.get(...)`. Identify the likely root cause, the relevant code path, and the first files to inspect. Cite files/functions. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_005_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_005 --agent codex --no-atlas
```

## 21. task_006_codex_with_atlas_r1_pilot_24_manual_v1

- Condition: `codex_with_atlas`
- Agent: `codex`
- Atlas enabled: `True`
- Task: `task_006`
- Repository: `home_assistant_core` @ `2989e6bcdf639489d2073276603a3c38d49eee21`
- Category: `negative_control`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In Home Assistant Core, is there a built-in integration/domain named `atlas_repository_context`? Verify from repository evidence; do not infer from package names. Cite files or absence checks. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_006_codex_with_atlas_r1_pilot_24_manual_v1 --condition codex_with_atlas --task-id task_006 --agent codex --atlas-enabled
```

## 22. task_006_codex_no_atlas_r1_pilot_24_manual_v1

- Condition: `codex_no_atlas`
- Agent: `codex`
- Atlas enabled: `False`
- Task: `task_006`
- Repository: `home_assistant_core` @ `2989e6bcdf639489d2073276603a3c38d49eee21`
- Category: `negative_control`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In Home Assistant Core, is there a built-in integration/domain named `atlas_repository_context`? Verify from repository evidence; do not infer from package names. Cite files or absence checks. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_006_codex_no_atlas_r1_pilot_24_manual_v1 --condition codex_no_atlas --task-id task_006 --agent codex --no-atlas
```

## 23. task_006_cursor_with_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_with_atlas`
- Agent: `cursor`
- Atlas enabled: `True`
- Task: `task_006`
- Repository: `home_assistant_core` @ `2989e6bcdf639489d2073276603a3c38d49eee21`
- Category: `negative_control`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Enable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are visible/available.
- Do not paste Atlas output manually into the prompt.
- Record every Atlas MCP call and Atlas latency if visible.

Prompt:

```text
In Home Assistant Core, is there a built-in integration/domain named `atlas_repository_context`? Verify from repository evidence; do not infer from package names. Cite files or absence checks. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_006_cursor_with_atlas_r1_pilot_24_manual_v1 --condition cursor_with_atlas --task-id task_006 --agent cursor --atlas-enabled
```

## 24. task_006_cursor_no_atlas_r1_pilot_24_manual_v1

- Condition: `cursor_no_atlas`
- Agent: `cursor`
- Atlas enabled: `False`
- Task: `task_006`
- Repository: `home_assistant_core` @ `2989e6bcdf639489d2073276603a3c38d49eee21`
- Category: `negative_control`
- Difficulty: `medium`

Checklist:
- Start a fresh agent session.
- Disable Atlas MCP before submitting the prompt.
- Confirm Atlas tools are absent/unavailable.
- Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.
- Record proof of the disabled condition in notes or screenshot/log reference.

Prompt:

```text
In Home Assistant Core, is there a built-in integration/domain named `atlas_repository_context`? Verify from repository evidence; do not infer from package names. Cite files or absence checks. Answer with sections: Summary, Evidence files, Reasoning, Caveats, Confidence.
```

Capture command template:

```powershell
py -3 benchmarks\agent_atlas_comparison\scripts\capture_run.py --run-id task_006_cursor_no_atlas_r1_pilot_24_manual_v1 --condition cursor_no_atlas --task-id task_006 --agent cursor --no-atlas
```
