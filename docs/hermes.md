# Hermes local-model setup

Prepared on 2026-10-02. The user completed the initial inference check on `ollama2`; Hermes Agent installation remains pending. No remote commands have been executed by Codex.

## Scope

First evaluate documentation assistance and manually requested, read-only health reports. Use `ollama2` (`192.168.0.167`) for inference, starting with its installed `llama3.2:3b`. This is a compatibility baseline, not an established recommendation for agent quality.

The user has authorized treating Hermes as the sole intended use of `ollama2` for now. Inference tuning may therefore target this workload; no competing clients are assumed. This is an intended allocation, not independently verified absence of client traffic. The eventual interface is a Discord bot, to be added after basic CLI and tool-use validation.

Proposed initial Hermes location: `ollama2`, under a regular non-root account. Use the local endpoint `http://127.0.0.1:11434/v1`. No production SSH credentials, Home Assistant tokens, scheduled jobs, or messaging integrations are needed for the first test. Natural-language restrictions alone do not enforce read-only access; initial health data should be manually collected, and any later live access must use appropriately restricted tools/accounts.

## First inference check

On `ollama2`, make a separate model alias with a 65536-token context setting. This preserves the original model configuration and does not restart Ollama. It loads the Hermes model and consumes inference resources.

```bash
hostname
cat > /tmp/hermes.Modelfile <<'EOF'
FROM llama3.2:3b
PARAMETER num_ctx 65536
EOF
ollama create hermes -f /tmp/hermes.Modelfile
curl -fsS --max-time 300 http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes","messages":[{"role":"user","content":"Reply with one short sentence confirming you can respond."}],"stream":false,"keep_alive":"5m","options":{"num_ctx":65536,"num_predict":64}}'
curl -fsS --max-time 10 http://127.0.0.1:11434/api/ps
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
```

Inspect the response, loaded context length, GPU allocation, and generation timings. A successful short response does not validate long-context reasoning or tool calling. Do not proceed with more integrations until a normal Hermes conversation and a controlled tool-use test work.

## Installation after inference check

### Recorded inference result — 2026-10-02

The `hermes:latest` alias (Llama 3.2 3B, Q4_K_M) returned "I'm ready to assist you." at an observed loaded context length of 65536.

- Total request duration: 6.58 seconds, including 5.91 seconds loading.
- Prompt evaluation: 35 tokens in 0.313 seconds.
- Generation: 8 tokens in 0.359 seconds, approximately 22.3 tokens/second.
- Ollama reported total loaded size: 10,116,019,873 bytes (approximately 9.42 GiB).
- Ollama reported VRAM allocation: 4,782,030,847 bytes (approximately 4.45 GiB).
- NVIDIA reported GPU memory used: 4652 MiB of 6144 MiB.

This verifies basic inference and a configured 64K context allocation, not successful processing of a full 64K prompt, complete GPU residency, or agent tool-use quality. Hermes chat and tool validation remain pending.

### Hermes CLI result — 2026-10-03

The user installed Hermes and connected the custom Chat Completions endpoint. The initial response drifted toward file-editing instructions. `/reasoning none --global` successfully saved the disabled reasoning setting and removed the prior unsupported-medium warning. Two subsequent requests to answer `2 + 2` with only the number instead returned `{"name": null, "parameters": {}}`. The Llama 3.2 3B alias therefore has not passed basic instruction-following in the Hermes prompt/tool configuration. Do not treat successful raw Ollama inference as successful agent validation. Model replacement and configuration isolation remain next steps; Discord setup is pending.

The user subsequently replaced the `hermes` alias with `qwen3.5:4b`. `ollama show` confirmed Qwen35, 4.7B parameters, Q4_K_M, maximum context 262144, and configured `num_ctx` 65536. Effective model defaults shown were temperature 1, presence penalty 1.5, top-k 20, and top-p 0.95. `ollama ps` reported 6.1 GB loaded size with 29%/71% CPU/GPU placement; NVIDIA reported 4958 MiB used out of 6144 MiB. The basic arithmetic check returned `4`, but a disk-growth advice check produced invalid commands and has not passed. A filtered search of `~/.hermes/config.yaml` found no explicit temperature, presence/frequency penalty, top-p, or top-k settings. Lower-temperature, zero-presence-penalty model settings are the proposed next comparison, not yet applied or validated.

The user applied temperature 0.2 and presence penalty 0 to the 4B alias; disk-growth advice still contained invalid commands. The alias was then rebuilt from `qwen3.5:9b` with the same settings and 65536 context. User-supplied runtime inventory reported alias ID `fa98b9e88c27`, 8.5 GB loaded size, 54%/46% CPU/GPU placement, and 4858 MiB GPU memory used. The 9B responses improved but still failed command correctness and explicit constraints, including invented journal flags and failure to stay on one filesystem. Repeated warm responses took roughly 18–24 seconds in the displayed UI; these are observations rather than controlled benchmarks.

Current assessment: generated shell commands are not reliable enough for live operational use. The proposed initial Discord scope is explanation of manually supplied health output and curated documentation, with execution tools disabled. Tool configuration, actual tool activity, and Discord access restrictions are not yet verified. Correct baseline Ubuntu checks for the evaluated question are `df -h`, `du -xhd1 /var` (permission coverage may require elevated collection), and `journalctl --disk-usage`.

The user disabled CLI toolsets `terminal`, `file`, `vision`, and `skills`; Hermes acknowledged the change and reset the session. Discord toolsets remain unverified. Fully local inference is an explicit user requirement.

DeepSeek-R1 8B was downloaded and compared through the same alias at 65536 context. It omitted the filesystem-boundary flag on both responses, displayed roughly 1K prompt tokens, took about a minute, and reported an auxiliary title-generation timeout. The alias was restored to Qwen3.5 9B with temperature 0.2 and presence penalty 0. A fresh process displayed 743 prompt tokens and about 16 seconds response time, but returned `df -i /` for capacity and again omitted `du -x`. Neither model passed this command-generation check. Further model swaps are deferred; Qwen3.5 9B is the current provisional backend for restricted chat, not a validated operations agent. Discord setup is the next step, with its own access and tool configuration to be inspected.

Use the official Linux installer under the intended regular account:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes setup
```

Choose Blank Slate if offered, then configure a custom endpoint at `http://127.0.0.1:11434/v1` with model `hermes`. Retain an effective context length of 65536. The local Ollama endpoint does not require a real provider API key; if a client requires a nonempty placeholder, use `ollama`. Inspect the actual installed wizard before finalizing additional settings.

## Evaluation tasks

The persistent user-owned `agent.system_prompt` overlay was saved using JSON string encoding after plain multiline input failed the CLI's YAML parsing. Local gateway source references confirmed support despite the config-key validation warning. A fresh Discord conversation correctly identified Skip as a wallaby and recalled Homepage, Home Assistant and yggdrasil as priorities. The user subsequently applied the wallaby personality refinement and accepted it. The next implementation is manually collected endpoint reporting; see [`skip-health-reports.md`](skip-health-reports.md).

### Discord progress — 2026-10-03

The gateway connected as Skip. Initial startup notification failed with Discord Missing Access for the configured home channel; home-channel correction is not yet confirmed. Channel thread creation initially failed, then command responses succeeded after permission troubleshooting. The user selected Discord tool configuration and was instructed to deselect terminal, file, vision, and skills and restart. A subsequent fresh Discord conversation returned `I can respond.` to the basic chat check. A post-save tool inventory is still pending; no live system access has been validated. A compact, non-secret reference is maintained in [`hermes-reference.txt`](hermes-reference.txt) for direct pasting into the conversation. This supplies session context only, not persistent memory or automatic document synchronization.

1. Basic chat: verify the endpoint, selected model, and effective context.
2. Documentation: supply a curated copy of the homelab Markdown docs and request a cited list of inventory gaps without editing source files. Measure factual accuracy and whether uncertainty is retained.
3. Health report: supply manually collected status output and request a summary distinguishing service state, backup verification, and missing evidence.
4. Controlled tool test: use a disposable working directory and restricted runtime before connecting live homelab services. Measure tool-call correctness and compliance with scope.

## Tools and integrations

Skip's MCP servers, their scripts and credentials, and the system prompt rule blocks are inventoried in [`skip-mcp.md`](skip-mcp.md). The Home Assistant bridge (solar, battery, feed-in price, Backrest plans, Frigate reviews) is in [`skip-homeassistant.md`](skip-homeassistant.md).

## References

- [Official Hermes quickstart](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/quickstart.md)
- [Ollama instance inventory](ollama.md)
