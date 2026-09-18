# DeGro on Vast.ai with local Ollama

This bundle runs the existing SymCode -> DeGro pipeline against an Ollama
server on the rented GPU. It does not use or copy the project's cloud API keys.

## Model name

The default is `qwen3:8b`, the exact 8B Qwen tag available in Ollama. Qwen2
does not have an 8B tag; use `qwen2:7b-instruct` if the experiment specifically
requires Qwen2.

## 1. Build and upload from the Mac

From the `Son` directory:

```bash
bash vastai/build_bundle.sh
scp -i ~/.ssh/id_ed25519_vastai -P VAST_PORT \
  vastai/dist/degro-vastai.tar.gz root@VAST_IP:/workspace/
```

Use the port and IP from the Vast.ai **Connect** button. `scp` uses uppercase
`-P` for the port.

## 2. Extract and set up on Vast.ai

```bash
ssh -i ~/.ssh/id_ed25519_vastai -p VAST_PORT root@VAST_IP
mkdir -p /workspace/degro
tar -xzf /workspace/degro-vastai.tar.gz -C /workspace/degro
cd /workspace/degro
bash Son/vastai/setup.sh qwen3:8b
```

Setup verifies CUDA, installs Ollama and Python dependencies into Vast.ai's
`/venv/main`, registers Ollama as a Supervisor-managed service, binds it to
localhost only, and pulls the model. Keeping Ollama on localhost avoids exposing
an unauthenticated inference endpoint to the internet.

## 3. Smoke test

```bash
cd /workspace/degro
bash Son/vastai/smoke_test.sh qwen3:8b
python Son/vastai/status.py Son/vastai/results/smoke.jsonl
ollama ps
```

`ollama ps` should show the model using the GPU. The smoke test processes two
MATH-500 examples and writes resumable JSONL output.

## 4. Full run

Use `tmux` so the run survives an SSH disconnect:

```bash
apt-get update && apt-get install -y tmux
tmux new -s degro
cd /workspace/degro
bash Son/vastai/run_all.sh qwen3:8b
```

Detach with `Ctrl-b`, then `d`. Reattach later with:

```bash
tmux attach -t degro
```

The default full run covers every bundled dataset, uses one Ollama worker, an
8K context, and writes to:

```text
Son/vastai/results/qwen3_8b_symcode_degro.jsonl
```

It is safe to rerun the same command: completed `(dataset, id, model)` jobs are
read from the JSONL file and skipped.

Examples:

```bash
# MATH-500 only
bash Son/vastai/run_all.sh qwen3:8b --datasets math500

# First 10 examples from each selected dataset
bash Son/vastai/run_all.sh qwen3:8b --datasets math500 alg514 --limit 10

# True Qwen2 experiment (7B, because Qwen2 has no 8B tag)
bash Son/vastai/setup.sh qwen2:7b-instruct
bash Son/vastai/run_all.sh qwen2:7b-instruct --datasets math500
```

Start with one worker. Increasing `--workers` can increase throughput on a large
GPU, but parallel Ollama requests also increase VRAM use and may reduce
reproducibility.

## Troubleshooting

```bash
nvidia-smi
curl http://127.0.0.1:11434/api/tags
ollama list
ollama ps
supervisorctl status ollama-degro
```

If the model is not installed, run `ollama pull MODEL`. If Ollama is not
running, restart the managed service:

```bash
supervisorctl restart ollama-degro
```

The Vast.ai instance may not have a persistent workspace volume. Check with
`vast-capabilities | jq '.instance.workspace_is_volume'` and copy result files
back to your Mac before recycling or destroying the instance.
