---
name: modal
description: Cloud computing platform for running Python on GPUs and serverless infrastructure. Use when deploying AI/ML models, running GPU-accelerated workloads, serving web endpoints, scheduling batch jobs, or scaling Python code to the cloud. Use this skill whenever the user mentions Modal, serverless GPU compute, deploying ML models to the cloud, serving inference endpoints, running batch processing in the cloud, or needs to scale Python workloads beyond their local machine. Also use when the user wants to run code on H100s, A100s, or other cloud GPUs, or needs to create a web API for a model.
license: Apache-2.0
metadata:
  skill-author: K-Dense Inc.
---

# Modal

## Overview

Modal is a cloud platform for running Python code serverlessly, with a focus on AI/ML workloads. Key capabilities:
- **GPU compute** on demand (T4, L4, A10, L40S, A100, H100, H200, B200)
- **Serverless functions** with autoscaling from zero to thousands of containers
- **Custom container images** built entirely in Python code
- **Persistent storage** via Volumes for model weights and datasets
- **Web endpoints** for serving models and APIs
- **Scheduled jobs** via cron or fixed intervals
- **Sub-second cold starts** for low-latency inference

Everything in Modal is defined as code — no YAML, no Dockerfiles required (though both are supported).

## When to Use This Skill

Use this skill when:
- Deploy or serve AI/ML models in the cloud
- Run GPU-accelerated computations (training, inference, fine-tuning)
- Create serverless web APIs or endpoints
- Scale batch processing jobs in parallel
- Schedule recurring tasks (data pipelines, retraining, scraping)
- Need persistent cloud storage for model weights or datasets
- Want to run code in custom container environments
- Build job queues or async task processing systems

## Installation and Authentication

### Install

```bash
uv pip install modal
```

### Authenticate

Prefer existing credentials before creating new ones:

1. Check whether `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` are already present in the current environment.
2. If not, check for those values in a local `.env` file and load them if appropriate for the workflow.
3. Only fall back to interactive `modal setup` or generating fresh tokens if neither source already provides credentials.

```bash
modal setup
```

This opens a browser for authentication. For CI/CD or headless environments, use environment variables:

```bash
export MODAL_TOKEN_ID=<your-token-id>
export MODAL_TOKEN_SECRET=<your-token-secret>
```

If tokens are not already available in the environment or `.env`, generate them at https://modal.com/settings

Modal offers a free tier with $30/month in credits.

**Reference**: See `references/getting-started.md` for detailed setup and first app walkthrough.

## Core Concepts

### App and Functions

A Modal `App` groups related functions. Functions decorated with `@app.function()` run remotely in the cloud:

```python
import modal

app = modal.App("my-app")

@app.function()
def square(x):
    return x ** 2

@app.local_entrypoint()
def main():
    # .remote() runs in the cloud
    print(square.remote(42))
```

Run with `modal run script.py`. Deploy with `modal deploy script.py`.

**Reference**: See `references/functions.md` for lifecycle hooks, classes, `.map()`, `.spawn()`, and more.

### Container Images

Modal builds container images from Python code. The recommended package installer is `uv`:

```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install("torch==2.8.0", "transformers", "accelerate")
    .apt_install("git")
)

@app.function(image=image)
def inference(prompt):
    from transformers import pipeline
    pipe = pipeline("text-generation", model="meta-llama/Llama-3-8B")
    return pipe(prompt)
```

Key image methods:
- `.uv_pip_install()` — Install Python packages with uv (recommended)
- `.pip_install()` — Install with pip (fallback)
- `.apt_install()` — Install system packages
- `.run_commands()` — Run shell commands during build
- `.run_function()` — Run Python during build (e.g., download model weights)
- `.add_local_python_source()` — Add local modules
- `.env()` — Set environment variables

**Reference**: See `references/images.md` for Dockerfiles, micromamba, caching, GPU build steps.

### GPU Compute

Request GPUs via the `gpu` parameter:

```python
@app.function(gpu="H100")
def train_model():
    import torch
    device = torch.device("cuda")
    # GPU training code here

# Multiple GPUs
@app.function(gpu="H100:4")
def distributed_training():
    ...

# GPU fallback chain
@app.function(gpu=["H100", "A100-80GB", "A100-40GB"])
def flexible_inference():
    ...
```

Available GPUs: T4, L4, A10, L40S, A100-40GB, A100-80GB, H100, H200, B200, B200+

- Up to 8 GPUs per container (except A10: up to 4)
- L40S is recommended for inference (cost/performance balance, 48 GB VRAM)
- H100/A100 can be auto-upgraded to H200/A100-80GB at no extra cost
- Use `gpu="H100!"` to prevent auto-upgrade

**Reference**: See `references/gpu.md` for GPU selection guidance and multi-GPU training.

### Volumes (Persistent Storage)

Volumes provide distributed, persistent file storage:

```python
vol = modal.Volume.from_name("model-weights", create_if_missing=True)

@app.function(volumes={"/data": vol})
def save_model():
    # Write to the mounted path
    with open("/data/model.pt", "wb") as f:
        torch.save(model.state_dict(), f)

@app.function(volumes={"/data": vol})
def load_model():
    model.load_state_dict(torch.load("/data/model.pt"))
```

- Optimized for write-once, read-many workloads (model weights, datasets)
- CLI access: `modal volume ls`, `modal volume put`, `modal volume get`
- Background auto-commits every few seconds

**Reference**: See `references/volumes.md` for v2 volumes, concurrent writes, and best practices.

### Secrets

Securely pass credentials to functions:

```python
@app.function(secrets=[modal.Secret.from_name("my-api-keys")])
def call_api():
    import os
    api_key = os.environ["API_KEY"]
    # Use the key
```

Create secrets via CLI: `modal secret create my-api-keys API_KEY=sk-xxx`

Or from a `.env` file: `modal.Secret.from_dotenv()`

**Reference**: See `references/secrets.md` for dashboard setup, multiple secrets, and templates.

### Web Endpoints

Serve models and APIs as web endpoints:

```python
@app.function()
@modal.fastapi_endpoint()
def predict(text: str):
    return {"result": model.predict(text)}
```

- `modal serve script.py` — Development with hot reload and temporary URL
- `modal deploy script.py` — Production deployment with permanent URL
- Supports FastAPI, ASGI (Starlette, FastHTML), WSGI (Flask, Django), WebSockets
- Request bodies up to 4 GiB, unlimited response size

**Reference**: See `references/web-endpoints.md` for ASGI/WSGI apps, streaming, auth, and WebSockets.

### Gradio Deployment Pattern (Recommended for Conversational AI)

Gradio works reliably with `@modal.asgi_app()` for serverless deployments. Chainlit does NOT work on Modal (see `chainlit-modal-deployment` skill for details).

**Critical Pattern**:
```python
import modal

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "gradio==4.44.1",
    "huggingface_hub==0.19.4"  # Pin this version! Gradio 4.44.1 expects HfFolder
)

app = modal.App("my-gradio-app", image=image)

@app.function(max_containers=1)  # Prevents scaling explosions
@modal.asgi_app()
def ui():
    from gradio import gr  # ✅ Import INSIDE function, not at module level
    
    with gr.Blocks() as demo:
        # ... build UI ...
        pass
    
    demo.launch(prevent_thread_lock=True)  # ✅ Initialize config before returning
    return demo.app  # ✅ Return demo.app, NOT demo or tuple
```

**Key Rules**:
1. **Import gradio inside `ui()` function** — module-level imports fail in Modal's build environment
2. **Pin `huggingface_hub==0.19.4`** for Gradio 4.44.1 — newer versions removed `HfFolder` that Gradio expects
3. **Use `max_containers=1`** — replaces deprecated `concurrency_limit`, prevents 22-container explosions
4. **Call `demo.launch(prevent_thread_lock=True)`** before returning — initializes Gradio config
5. **Return `demo.app`** — NOT `demo` (returns tuple) or `demo.launch()` (returns None)

**Browser Cache Pitfall**:
After deployment, users often see old UI versions. The app deployed successfully but browser cache serves stale content.
- **Fix**: Hard refresh with `Cmd+Shift+R` (Mac) / `Ctrl+Shift+R` (Windows)
- **Alternative**: Open in incognito/private window to bypass cache entirely
- **Verification**: `curl -s https://your-app.modal.run | grep "new-content"` to check if new content is actually live

**Cache Busting for Forced Rebuilds**:
If Modal reuses cached containers despite code changes, force a rebuild:
```python
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "gradio==4.44.1"
).run_commands(["echo 'Cache bust v2'"])  # Forces image rebuild
```

## Chainlit + LangGraph Integration
For deploying LangGraph/LangChain agentic apps with Chainlit UI on Modal:

### Thread Metadata Persistence (Chainlit 2.x)
- Chainlit 2.x does not reliably expose data layer via decorators; use a global `DATA_LAYER` variable for `SQLiteDataLayer`
- **Critical**: Chainlit 2.x expects `config.code.data_layer` to be a **callable factory function**, not an instance. Assigning the instance directly causes `TypeError: 'SQLiteDataLayer' object is not callable`. Fix:
  ```python
  chainlit_config.config.code.data_layer = lambda: DATA_LAYER
  ```
- Store `workspace_folder` in thread metadata via `DATA_LAYER.update_thread()`
- Fix `WebSocketSession` errors by removing invalid `cl.context.session.thread` access; retrieve metadata on resume via `DATA_LAYER.get_thread()`

### Modal Image Setup for Agentic Apps
- Include all LangChain/LangGraph/Chainlit dependencies in Modal image pip installs (e.g., `beautifulsoup4`, `langchain-community`, `langchain-chroma`)
- Add domain-specific packages (biopython, scanpy, rdkit) as needed for bioinformatics/cheminformatics agents

### Common Pitfalls
- **Traceloop SDK + Python 3.12**: Patch `traceloop/sdk/utils/package_check.py` to catch `TypeError` from `importlib_metadata` returning `None`
- **Model Mismatches**: Standardize embedding models (e.g., `openai/text-embedding-3-small`) and use valid OpenRouter LLM models (e.g., `anthropic/claude-3-haiku`)
- **Persistent Storage**: Mount Modal volume at `/root/persistent` for Chainlit SQLite databases (`chainlit_v2.db`, `conversation_history.db`)
- **Chainlit Environment Variables on Modal**: Mounted `.env` files via `modal.Image.add_local_file()` are not automatically loaded into the Modal runtime. To apply Chainlit settings (e.g., `CHAINLIT_AUTH_ENABLED=false`), explicitly load the `.env` file in the Modal function that starts Chainlit:
  ```python
  from dotenv import load_dotenv
  load_dotenv("/root/.env")  # Path to mounted .env file in Modal container
  ```
- **Auth Disabling**: Set `CHAINLIT_AUTH_ENABLED=false` in `.env` and load it via `load_dotenv` to avoid blank login pages for public apps.

### Scheduled Jobs

Run functions on a schedule:

```python
@app.function(schedule=modal.Cron("0 9 * * *"))  # Daily at 9 AM UTC
def daily_pipeline():
    # ETL, retraining, scraping, etc.
    ...

@app.function(schedule=modal.Period(hours=6))
def periodic_check():
    ...
```

Deploy with modal deploy script.py to activate the schedule.

- modal.Cron("...") — Standard cron syntax, stable across deploys
- modal.Period(hours=N) — Fixed interval, resets on redeploy
- Monitor runs in the Modal dashboard

### Computational UX & Telemetry (User Preference)

When implementing UIs or dashboards that trigger Modal jobs, adhere to these UX principles:
- **Active Telemetry**: Ensure the UI shows an **accelerated animation** (e.g., 1.2s scan pulse instead of 4s) when a Modal task is active to signal high-throughput processing.
- **Color Coding**: Use a distinct color (e.g., **Rose-Red / #F43F5E**) for cloud/Modal task animations to distinguish them from local/standard tasks (usually Cyan).
- **Explicit Labeling**: Clearly label the active hardware provider: `MODAL.COM • [TASK_NAME]`.

### Bioinformatics & Scientific Workflow

- **Container Selection**: For command-line scientific tools (Clustal Omega, Samtools, etc.), prioritize pulling from **BioContainers** images (e.g., `biocontainers/clustal-omega`) via `modal.Image.from_registry()` instead of manual installations.
- **Scaling Heavy Tasks**: For multi-species alignments or large genomic datasets, leverage `.map()` to parallelize across hundreds of Modal containers.

**Reference**: See references/scheduled-jobs.md for cron syntax and management.

### Scaling and Concurrency

Modal autoscales containers automatically. Configure limits:

```python
@app.function(
    max_containers=100,    # Upper limit
    min_containers=2,      # Keep warm for low latency
    buffer_containers=5,   # Reserve capacity
    scaledown_window=300,  # Idle seconds before shutdown
)
def process(data):
    ...
```

Process inputs in parallel with `.map()`:

```python
results = list(process.map([item1, item2, item3, ...]))
```

Enable concurrent request handling per container:

```python
@app.function()
@modal.concurrent(max_inputs=10)
async def handle_request(req):
    ...
```

**Reference**: See `references/scaling.md` for `.map()`, `.starmap()`, `.spawn()`, and limits.

### Resource Configuration

```python
@app.function(
    cpu=4.0,              # Physical cores (not vCPUs)
    memory=16384,         # MiB
    ephemeral_disk=51200, # MiB (up to 3 TiB)
    timeout=3600,         # Seconds
)
def heavy_computation():
    ...
```

Defaults: 0.125 CPU cores, 128 MiB memory. Billed on max(request, usage).

**Reference**: See `references/resources.md` for limits and billing details.

## Classes with Lifecycle Hooks

For stateful workloads (e.g., loading a model once and serving many requests):

```python
@app.cls(gpu="L40S", image=image)
class Predictor:
    @modal.enter()
    def load_model(self):
        self.model = load_heavy_model()  # Runs once on container start

    @modal.method()
    def predict(self, text: str):
        return self.model(text)

    @modal.exit()
    def cleanup(self):
        ...  # Runs on container shutdown
```

Call with: `Predictor().predict.remote("hello")`

## Common Workflow Patterns

### GPU Model Inference Service

```python
import modal

app = modal.App("llm-service")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install("vllm")
)

@app.cls(gpu="H100", image=image, min_containers=1)
class LLMService:
    @modal.enter()
    def load(self):
        from vllm import LLM
        self.llm = LLM(model="meta-llama/Llama-3-70B")

    @modal.method()
    @modal.fastapi_endpoint(method="POST")
    def generate(self, prompt: str, max_tokens: int = 256):
        outputs = self.llm.generate([prompt], max_tokens=max_tokens)
        return {"text": outputs[0].outputs[0].text}
```

### Batch Processing Pipeline

```python
app = modal.App("batch-pipeline")
vol = modal.Volume.from_name("pipeline-data", create_if_missing=True)

@app.function(volumes={"/data": vol}, cpu=4.0, memory=8192)
def process_chunk(chunk_id: int):
    import pandas as pd
    df = pd.read_parquet(f"/data/input/chunk_{chunk_id}.parquet")
    result = heavy_transform(df)
    result.to_parquet(f"/data/output/chunk_{chunk_id}.parquet")
    return len(result)

@app.local_entrypoint()
def main():
    chunk_ids = list(range(100))
    results = list(process_chunk.map(chunk_ids))
    print(f"Processed {sum(results)} total rows")
```

### Scheduled Data Pipeline

```python
app = modal.App("etl-pipeline")

@app.function(
    schedule=modal.Cron("0 */6 * * *"),  # Every 6 hours
    secrets=[modal.Secret.from_name("db-credentials")],
)
def etl_job():
    import os
    db_url = os.environ["DATABASE_URL"]
    # Extract, transform, load
    ...
```

## Complete CLI Reference

### Modal Setup & Auth
| Command | Description |
|---------|-------------|
| `modal setup` | Bootstrap Modal configuration (interactive auth) |
| `modal setup --profile TEXT` | Setup with a specific profile |
| `modal token info` | Display current token information |
| `modal token new` | Create new token via authenticated web session |
| `modal token set --token-id ID --token-secret SECRET` | Set credentials directly |
| `modal profile activate PROFILE` | Switch between Modal profiles |
| `modal profile current` | Print currently active profile |
| `modal profile list` | Show all profiles and highlight active one |
| `modal config set-environment NAME` | Set default environment for active profile |
| `modal config show` | Show current configuration values |

### Running & Deploying
| Command | Description |
|---------|-------------|
| `modal run my_app.py` | Run a function or local entrypoint |
| `modal run my_app.py::function_name` | Run a specific function by ref |
| `modal run -m my_package.my_mod` | Run a module as path |
| `modal serve my_app.py` | Dev server with hot reload, temporary URL (-dev suffix) |
| `modal deploy my_app.py` | Deploy to production (permanent URL) |
| `modal deploy --name NAME` | Deploy with a specific name |
| `modal deploy --tag VERSION` | Tag the deployment with a version |
| `modal deploy --stream-logs` | Stream logs from the app upon deployment |
| `modal bootstrap [NAME]` | Initialize a sample Modal app |
| `modal changelog` | Fetch release notes |
| `modal changelog --since 1.2.0` | Show changes since a version |
| `modal changelog --version 1.2.0` | Show changes in a specific version |

### App Management
| Command | Description |
|---------|-------------|
| `modal app list` | List running, deployed, or recently stopped apps |
| `modal app stop NAME` | Permanently stop an app and terminate containers |
| `modal app logs NAME` | Fetch or stream app logs |
| `modal app history NAME` | Show deployment history |
| `modal app dashboard NAME` | Open app dashboard page in browser |
| `modal app rollback NAME` | Redeploy a previous version |
| `modal app rollover NAME` | Redeploy to get new containers without code changes |
| `modal dashboard` | Open Modal Dashboard in browser |

### Volume Management
| Command | Description |
|---------|-------------|
| `modal volume create NAME` | Create a named persistent volume |
| `modal volume list` | List all named volumes |
| `modal volume ls NAME [PATH]` | List files in a volume |
| `modal volume get NAME REMOTE_PATH` | Download file from volume |
| `modal volume put NAME LOCAL_PATH [REMOTE_PATH]` | Upload file to volume |
| `modal volume delete NAME` | Delete a named volume and all its data |
| `modal volume rm NAME PATH` | Remove a file or directory from a volume |
| `modal volume cp NAME SRC DEST` | Copy within a volume |
| `modal volume dashboard NAME` | Open volume dashboard in browser |

### Secret Management
| Command | Description |
|---------|-------------|
| `modal secret create NAME K=V [...]` | Create a new secret |
| `modal secret create --env ENV NAME K=V` | Create secret in specific environment |
| `modal secret list` | List published secrets |
| `modal secret delete NAME` | Delete a named secret |

### Queue Management
| Command | Description |
|---------|-------------|
| `modal queue create NAME` | Create a named Queue |
| `modal queue list` | List all named Queues |
| `modal queue len NAME` | Print queue length (or partition length) |
| `modal queue peek NAME [N]` | Print next N items without removing |
| `modal queue clear NAME` | Clear all data in a queue |
| `modal queue delete NAME` | Delete a named Queue and all data |

### Dict Management
| Command | Description |
|---------|-------------|
| `modal dict create NAME` | Create a named Dict |
| `modal dict list` | List all named Dicts |
| `modal dict get NAME KEY` | Print value for a specific key |
| `modal dict items NAME` | Print all contents of a Dict |
| `modal dict clear NAME` | Clear all data in a Dict |
| `modal dict delete NAME` | Delete a named Dict and all data |

### Container Management
| Command | Description |
|---------|-------------|
| `modal container list` | List all currently running containers |
| `modal container exec ID COMMAND` | Execute a command in a container |
| `modal container exec --pty ID COMMAND` | Execute with PTY (interactive) |
| `modal container logs ID` | Fetch or stream logs for a specific container |
| `modal container stop ID` | Terminate a running container |

### Environment Management
| Command | Description |
|---------|-------------|
| `modal environment create NAME` | Create a new environment |
| `modal environment list` | List all environments |
| `modal environment delete NAME` | Delete an environment and all its apps |

### Billing
| Command | Description |
|---------|-------------|
| `modal billing report --start DATE --end DATE` | Generate billing report |
| `modal billing report --for today` | Billing for today |
| `modal billing report --for 'last month'` | Billing for last month |

### Shell
| Command | Description |
|---------|-------------|
| `modal shell IMAGE_REF` | Open a shell in a Modal container |

## API Reference (Full)

### Core Classes

#### modal.App

The main unit of deployment. Groups related functions and classes together.

```python
app = modal.App("my-app")

# Optional tags for organization
app = modal.App("my-app", tags={"team": "ml", "project": "inference"})
```

**Registration decorators:**

| Decorator | Description |
|-----------|-------------|
| `@app.function(**kwargs)` | Register a serverless function |
| `@app.cls(**kwargs)` | Register a stateful class with lifecycle hooks |
| `@app.local_entrypoint()` | Mark a function as the local entry point for `modal run` |

**Key methods:**

| Method | Description |
|--------|-------------|
| `.deploy(name)` | Deploy the app to production |
| `.spawn(name)` | Create a new app instance |
| `.stop()` | Stop all containers for the app |
| `.get_function(name)` | Get a registered function by name |
| `.get_cls(name)` | Get a registered class by name |

Internally, `modal.App` syncs object identities across processes (local Python + all containers), manages log collection, and serves as the unit of deployment.

#### modal.Function

The basic unit of serverless execution on Modal. Functions are typically registered via `@app.function()`.

```python
@app.function(gpu="L40S", image=image, timeout=300)
def my_func(data: str):
    return process(data)
```

**Function parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | Image | `None` | Container image to run in |
| `gpu` | str | `None` | GPU type (e.g., "H100", "L40S") |
| `cpu` | float | `0.125` | CPU cores (fractional) |
| `memory` | int | `128` | Memory in MiB |
| `ephemeral_disk` | int | `51200` | Ephemeral disk in MiB (up to 3 TiB) |
| `timeout` | int | `300` | Max execution time in seconds |
| `secrets` | list[Secret] | `[]` | Secrets to inject as env vars |
| `volumes` | dict | `{}` | Volumes to mount |
| `network_file_systems` | dict | `{}` | NFS mounts (deprecated) |
| `schedule` | Cron/Period | `None` | Schedule for recurring execution |
| `max_containers` | int | `100` | Upper autoscaling limit |
| `min_containers` | int | `0` | Minimum warm containers |
| `buffer_containers` | int | `0` | Reserved container capacity |
| `scaledown_window` | int | `300` | Idle seconds before scale-down |
| `retries` | int/Retries | `0` | Retry policy |
| `name` | str | `None` | Function name (defaults to decorated name) |
| `cloud` | str | `None` | Cloud provider preference |
| `region` | str/list | `None` | Region(s) to run on |
| `allow_cross_region_volumes` | bool | `False` | Allow volumes from other regions |

**Execution methods:**

| Method | Description |
|--------|-------------|
| `.remote(*args)` | Execute in the cloud (synchronous, blocks) |
| `.local(*args)` | Execute locally (for testing) |
| `.spawn(*args)` | Execute asynchronously, returns `FunctionCall` |
| `.map(inputs)` | Parallel execution over an iterable |
| `.starmap(inputs)` | Parallel execution with tuple-unpacked args |
| `.for_each(inputs)` | Fire-and-forget parallel execution |
| `.from_name(app_name, fn_name)` | Reference a deployed function |
| `.update_autoscaler(**kwargs)` | Dynamically update scaling parameters |
| `.is_hydrated()` | Check if function object is synced with server |

#### modal.FunctionCall

A handle to an asynchronously spawned function call, similar to a Future/Promise.

```python
call = my_func.spawn(data)
# Later:
result = call.get()  # Blocks until complete
```

| Method | Description |
|--------|-------------|
| `.get(timeout)` | Get result, optionally with timeout |
| `.get_call_id()` | Get the unique call ID |
| `.cancel()` | Cancel the running call |

#### modal.Cls

A serverless class with lifecycle hooks and method pooling. Use `@app.cls()`.

```python
@app.cls(gpu="L40S", image=image, min_containers=1)
class Predictor:
    @modal.enter()
    def load(self):
        self.model = load_model()

    @modal.method()
    def predict(self, text: str):
        return self.model(text)

    @modal.exit()
    def cleanup(self):
        pass
```

**Class parameters:** Same as `@app.function()`.

**Lifecycle hooks:**

| Decorator | When it runs | Description |
|-----------|-------------|-------------|
| `@modal.enter()` | Once per container start | Load model, open connections |
| `@modal.exit()` | Container shutdown | Cleanup resources |
| `@modal.method()` | Each method call | Expose as callable method (with `.remote()`) |
| `@modal.parameter()` | Class instantiation | Declare class-level parameters (like dataclass fields) |

**Usage patterns:**
- `Predictor().predict.remote("hello")` — Call method remotely
- `Predictor.with_options(gpu="H100")().predict.remote(...)` — Override class options

#### modal.Image

Defines the container environment. Do not construct directly — use factory methods.

**Factory methods:**

| Method | Description |
|--------|-------------|
| `modal.Image.debian_slim(python_version="3.11")` | Debian slim base |
| `modal.Image.from_registry("ubuntu:22.04", ...)` | Docker Hub image |
| `modal.Image.from_dockerfile(path, ...)` | Build from Dockerfile |
| `modal.Image.from_dockerfile_contents("FROM ubuntu...")` | Build from inline Dockerfile |
| `modal.Image.micromamba(python_version="3.11")` | Conda/mamba base image |
| `modal.Image.conda(environment_file=...)` | Conda environment from YAML |

**Builder methods (chainable):**

| Method | Description |
|--------|-------------|
| `.uv_pip_install(*packages)` | Install with uv (recommended, faster) |
| `.pip_install(*packages)` | Install with pip |
| `.pip_install_from_requirements(path)` | Install from requirements.txt |
| `.pip_install_from_pyproject(pyproject_path)` | Install from pyproject.toml |
| `.apt_install(*packages)` | Install system packages |
| `.apt_get_install(*packages)` | More configurable apt variant |
| `.run_commands(*commands)` | Run shell commands during build |
| `.run_function(fn)` | Run a Python function during build |
| `.env(dict)` | Set environment variables at build time |
| `.add_local_dir(local_path, remote_path)` | Add local directory to image |
| `.add_local_file(local_path, remote_path)` | Add local file to image |
| `.add_local_python_source(module)` | Add a local Python module |
| `.copy(image, src_path, dest_path)` | Copy from another image |
| `.dockerfile_commands(*cmds)` | Append raw Dockerfile instructions |
| `.imports()` | Context manager for remote dependency imports |

**Caching behavior:** Images are cached and only rebuilt when their definition changes. Use `.run_commands(["echo 'Cache bust v2'"])` to force a rebuild.

### Storage Classes

#### modal.Volume

Distributed, persistent file storage for sharing data between functions.

```python
vol = modal.Volume.from_name("my-vol", create_if_missing=True)

@app.function(volumes={"/data": vol})
def worker():
    with open("/data/file.txt", "w") as f:
        f.write("data")
    vol.commit()  # Persist changes
```

**Key characteristics:**
- Optimized for write-once, read-many workloads (model weights, datasets)
- Requires explicit `.commit()` to persist, explicit `.reload()` to see other containers' changes
- Concurrent writes to the same file: last-write-wins
- Background auto-commit every few seconds
- Cannot reload with open files

**Methods:**

| Method | Description |
|--------|-------------|
| `Volume.from_name(name, create_if_missing=True)` | Reference or create a volume |
| `.commit()` | Force immediate persist of changes |
| `.reload()` | Refresh to see other containers' writes |
| `.rename(new_name)` | Rename the volume |
| `.delete()` | Delete the volume |
| `.is_hydrated()` | Check server sync status |

**Volume filesystem operations** (accessed via `Volume.objects`):
- `.objects.listdir(path)` — List directory contents
- `.objects.readfile(path)` — Read file contents
- `.objects.writefile(path, data)` — Write file contents
- `.objects.remove(path)` — Remove file or directory
- `.objects.copy(src, dest)` — Copy within volume

#### modal.NetworkFileSystem

Legacy shared storage — deprecated, superseded by Volume.

```python
nfs = modal.NetworkFileSystem.from_name("my-nfs", create_if_missing=True)
@app.function(network_file_systems={"/mnt": nfs})
def f():
    ...
```

#### modal.CloudBucketMount

Mount cloud storage buckets (S3, GCS, Azure) directly into containers.

```python
modal.CloudBucketMount(
    bucket_name="my-s3-bucket",
    secret=modal.Secret.from_name("aws-secret"),
    read_only=True
)
```

| Parameter | Description |
|-----------|-------------|
| `bucket_name` | Name of the cloud bucket |
| `secret` | Modal Secret with cloud credentials |
| `read_only` | Mount as read-only (default: False) |
| `mount_path` | Path in container (optional) |

**Supported providers:** AWS S3 (via S3 Mountpoint), Cloudflare R2
- Optimized for reading large files sequentially
- Does NOT support every file operation (consult AWS S3 Mountpoint docs)

### Stateful Storage

#### modal.Dict

Distributed dictionary (key-value store) for Modal apps.

```python
d = modal.Dict.from_name("my-dict", create_if_missing=True)
d["key"] = "value"  # Works like a regular dict
print(d["key"])     # "value"
```

**Key characteristics:**
- Contents serialized by cloudpickle (any object)
- Supports Modal objects as values
- Can be read/written across different environments (with compatible library versions)

**Methods:**

| Method | Description |
|--------|-------------|
| `Dict.from_name(name, create_if_missing=True)` | Reference or create a Dict |
| `d[key]` | Get value by key |
| `d[key] = value` | Set value by key |
| `del d[key]` | Delete a key |
| `key in d` | Check key existence |
| `d.keys()` | Get all keys |
| `d.values()` | Get all values |
| `d.items()` | Get all key-value pairs |
| `d.get(key, default)` | Get with default |
| `d.put(key, value)` | Put (alias for __setitem__) |
| `d.put_if_new(key, value)` | Put only if key doesn't exist |
| `d.update({key: value})` | Batch update |
| `d.clear()` | Remove all items |
| `d.len()` | Number of items |
| `d.delete()` | Delete the entire Dict object |
| `d.is_hydrated()` | Check server sync |

**CLI:** `modal dict create`, `modal dict list`, `modal dict get`, `modal dict items`, `modal dict clear`, `modal dict delete`

#### modal.Queue

Distributed, FIFO queue for data flow.

```python
q = modal.Queue.from_name("my-queue", create_if_missing=True)
q.put("item1")
q.put({"complex": "object"}, partition="high-priority")
item = q.get(timeout=5)  # Blocks up to 5 seconds
```

**Methods:**

| Method | Description |
|--------|-------------|
| `Queue.from_name(name, create_if_missing=True)` | Reference or create a Queue |
| `q.put(item)` | Add item to queue |
| `q.put(item, partition="name")` | Add to a specific partition |
| `q.get()` | Get next item (blocks if empty) |
| `q.get(timeout=5)` | Get with timeout (raises if empty) |
| `q.get_nowait()` | Non-blocking get (raises immediately if empty) |
| `q.len()` | Total items across all partitions |
| `q.len(partition="name")` | Items in a specific partition |
| `q.peek()` | View next item without removing |
| `q.peek(n=5)` | View next N items |
| `q.clear()` | Remove all items |
| `q.clear(partition="name")` | Clear single partition |
| `q.delete()` | Delete the entire Queue object |
| `q.is_hydrated()` | Check server sync |

**CLI:** `modal queue create`, `modal queue list`, `modal queue len`, `modal queue peek`, `modal queue clear`, `modal queue delete`

### Security Classes

#### modal.Secret

Securely provide environment variables to containers.

```python
# From dashboard/CLI
secret = modal.Secret.from_name("my-keys")

# From dict (dev only — prints in logs!)
secret = modal.Secret.from_dict({"API_KEY": "sk-xxx"})

# From .env file
secret = modal.Secret.from_dotenv()

# With required keys validation
secret = modal.Secret.from_name("aws-secret", required_keys=["AWS_ACCESS_KEY_ID"])
```

**Methods:**

| Method | Description |
|--------|-------------|
| `Secret.from_name(name, required_keys=[])` | Reference a named secret |
| `Secret.from_dict(d)` | Create inline (dev only, not secure!) |
| `Secret.from_dotenv(path=".env")` | Load from a .env file |
| `.is_hydrated()` | Check server sync |
| `.delete()` | Delete the secret |

Secrets are scoped to environments. Access in functions: `os.environ["KEY_NAME"]`.

#### modal.Proxy

Static outbound IP address for containers (e.g., for database whitelisting).

```python
proxy = modal.Proxy.from_name("my-proxy", create_if_missing=True)
@app.function(proxy=proxy)
def db_query():
    ...
```

### Scheduling

#### modal.Cron

Standard cron syntax for scheduling.

```python
modal.Cron("* * * * *")      # Every minute
modal.Cron("0 9 * * *")      # Daily at 9 AM UTC
modal.Cron("0 */6 * * *")    # Every 6 hours
modal.Cron("30 4 * * 1-5")   # Weekdays at 4:30 AM
```

Schedules are stable across deploys (same string = same schedule identity).

#### modal.Period

Fixed-interval scheduling.

```python
modal.Period(hours=4)
modal.Period(minutes=15)
modal.Period(seconds=30)
modal.Period(days=1)
```

**Note:** Period schedules reset on redeploy (recomputed from deploy time).

### Web Endpoints

#### @modal.fastapi_endpoint()

Simple FastAPI-style endpoint for a single function.

```python
@app.function()
@modal.fastapi_endpoint(method="POST", docs=True)
def predict(data: dict):
    return {"result": model(data)}
```

**Parameters:**
- `method`: HTTP method (default: "GET")
- `label`: Custom URL label
- `custom_domains`: Custom domain names
- `docs`: Enable interactive docs (default: False)
- `requires_proxy_auth`: Require Modal-Key/Modal-Secret headers

#### @modal.asgi_app()

Full ASGI application (FastAPI, Starlette, FastHTML).

```python
@app.function(max_containers=1)
@modal.asgi_app()
def ui():
    from fastapi import FastAPI
    web_app = FastAPI()
    @web_app.get("/")
    def read_root():
        return {"Hello": "World"}
    return web_app
```

#### @modal.wsgi_app()

Full WSGI application (Flask, Django).

```python
@app.function()
@modal.wsgi_app()
def flask_app():
    from flask import Flask, request
    app = Flask(__name__)
    @app.route("/")
    def hello():
        return "Hello from Modal!"
    return app
```

#### @modal.web_server()

Run a custom web server (any framework that binds to a port).

```python
@app.function()
@modal.web_server(port=8000, startup_timeout=10)
def my_server():
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
```

**Parameters:**
- `port`: Port to serve on
- `startup_timeout`: Max seconds to wait for server start (default: 5)
- `label`: Custom URL label
- `custom_domains`: Custom domain names
- `requires_proxy_auth`: Require auth headers

### Function Modifiers

#### @modal.concurrent()

Enable multiple inputs processed concurrently by a single container.

```python
@app.function()
@modal.concurrent(max_inputs=10, target_inputs=5)
async def handle(req):
    ...
```

| Parameter | Description |
|-----------|-------------|
| `max_inputs` | Hard limit on concurrency per container |
| `target_inputs` | Autoscaler target concurrency |

#### @modal.batched()

Dynamically batch function inputs for efficiency.

```python
@app.function()
@modal.batched(max_batch_size=4, wait_ms=1000)
def batch_process(items):
    # items will be a list of accumulated inputs
    return [process(item) for item in items]
```

| Parameter | Description |
|-----------|-------------|
| `max_batch_size` | Maximum batch size |
| `wait_ms` | Max wait time in ms before dispatching partial batch |

### Sandbox

#### modal.Sandbox

Isolated execution environment — run arbitrary commands in a container.

```python
# Create and run
sandbox = modal.Sandbox.create(
    "python3", "-c", "print('hello')",
    image=modal.Image.debian_slim(),
    timeout=60,
    app=app  # Associate with app
)
result = sandbox.wait()  # Wait for completion

# Or use as context manager
with modal.Sandbox.create("sleep", "5") as sb:
    sb.wait()
```

**Key parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*args` | str | — | Command to run (CMD override) |
| `image` | Image | `None` | Container image |
| `app` | App | `None` | Associate with app (REQUIRED unless from container) |
| `name` | str | `None` | Optional name |
| `timeout` | int | `300` | Max lifetime in seconds |
| `idle_timeout` | int | `None` | Idle timeout before termination |
| `gpu` | str | `None` | GPU requirement |
| `cpu` | float | — | CPU cores |
| `memory` | int | — | Memory in MiB |
| `ephemeral_disk` | int | — | Ephemeral disk in MiB |
| `env` | dict | `None` | Environment variables |
| `secrets` | list | `[]` | Secrets to inject |
| `workdir` | str | `None` | Working directory |
| `cloud` | str | `None` | Cloud provider |
| `region` | str/list | `None` | Region(s) |
| `volumes` | dict | `{}` | Volumes to mount |
| `network_file_systems` | dict | `{}` | NFS mounts |
| `encrypted_ports` | list | `[]` | Exposed TLS ports |
| `force_build` | bool | `False` | Force image rebuild |
| `mounts` | list | `[]` | Additional mounts |
| `readiness_probe` | Probe | `None` | Readiness check |

**Methods:**

| Method | Description |
|--------|-------------|
| `Sandbox.create(*args, **kwargs)` | Create and start a sandbox |
| `.wait()` | Wait for sandbox to finish (returns exit code) |
| `.terminate()` | Force-terminate the sandbox |
| `.stop()` | Graceful stop |
| `.get_id()` | Get sandbox ID |
| `.exec(command, **kwargs)` | Execute additional commands inside |
| `.exec(command, pty=True)` | Execute with PTY |
| `.open()` | Open a shell-like interactive session |
| `.detach()` | Detach from sandbox (let it continue running) |
| `.mount_image(image)` | Mount an image inside sandbox |
| `.unmount_image(image)` | Unmount an image |
| `.stdout` | StreamReader for stdout |
| `.stderr` | StreamReader for stderr |
| `.returncode` | Exit code (available after wait) |
| `._experimental_snapshot()` | Create memory/filesystem snapshot |
| `.is_hydrated()` | Check server sync |

**Stream I/O:**
```python
sandbox = modal.Sandbox.create("python3", "-c", "print('hi')")
for chunk in sandbox.stdout:
    print(chunk, end="")
```

#### modal.SandboxSnapshot

[Early Preview] Store and restore sandbox state (filesystem + memory).

```python
snapshot = sandbox._experimental_snapshot()
# Later, restore from snapshot
```

#### modal.Probe

Health/readiness probes for sandboxes.

```python
# Wait until a file exists
readiness_probe = modal.Probe.with_exec(
    "sh", "-c", "test -f /tmp/ready"
)

# Wait until TCP port is accepting
readiness_probe = modal.Probe.with_tcp(8080)

sandbox = modal.Sandbox.create(
    "python3", "server.py",
    readiness_probe=readiness_probe
)
```

| Method | Description |
|--------|-------------|
| `Probe.with_exec(*cmd)` | Run a command to check readiness |
| `Probe.with_tcp(port)` | Check TCP port is accepting |

#### modal.forward()

Expose a port publicly from a running container (with TLS).

```python
from modal import forward

with forward(port=8080) as tunnel:
    print(f"Service available at {tunnel.url}")
    # ... keep running ...
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `port` | — | Port inside the container |
| `unencrypted` | False | Also expose unencrypted TCP socket |
| `h2_enabled` | False | Enable HTTP/2 |

Returns a `Tunnel` object with `.url` and `.tls_socket` properties.

#### modal.Tunnel

Reference to a forwarded port. Obtained from `modal.forward()`.

| Property | Description |
|----------|-------------|
| `.url` | Public HTTPS URL |
| `.tls_socket` | TLS socket for direct connection |
| `.host` | Tunnel host |
| `.port` | Tunnel port |

#### modal.interact()

Enable interactive user input inside a Modal container.

```python
@app.function()
def interactive_fn():
    modal.interact()  # Allows stdin interaction
    name = input("Enter name: ")
    print(f"Hello {name}")
```

### Networking

#### modal.CloudBucketMount

*(Described under "Storage Classes" above)*

### Utilities

#### modal.Client

Low-level client for Modal API. Useful for managing Modal on behalf of third-party users.

```python
client = modal.Client.from_credentials(token_id, token_secret)
client.hello()  # Connect and verify
```

#### modal.Environment

Manage Modal environments (sub-divisions of workspaces).

```python
env = modal.Environment.from_name("production")
env.name  # Environment name
```

**Manager methods** (via `Environment.objects`):
- `objects.create(name, restricted=False)` — Create environment
- `objects.list()` — List all environments
- `objects.delete(name)` — Delete environment

#### modal.billing

Billing information and cost tracking.

```python
report = await modal.billing.workspace_billing_report(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 31)
)
```

Returns `WorkspaceBillingReportItem` with: object_id, description, environment_name, interval_start, cost, tags.

#### modal.call_graph

Distributed tracing of function calls.

```python
# modal.call_graph.InputInfo — tracks function call tree
# modal.call_graph.InputStatus — enum (e.g., SUCCESS, FAILED)
```

### I/O Utilities

#### modal.file_io (Alpha)

[Alpha] File I/O handles for Sandbox filesystem API. Deprecated in favor of Sandbox.filesystem APIs.

#### modal.io_streams

Stream I/O for reading container stdout/stderr.

```python
class StreamReader:
    async def read(self) -> bytes: ...
    file_descriptor -> int  # 1=stdout, 2=stderr
```

Supports `async for` iteration over chunks.

#### modal.FilePatternMatcher

Match file paths against glob patterns (for mounts, volume operations).

```python
matcher = modal.FilePatternMatcher("*.py")
assert matcher(Path("foo.py"))
negated = ~matcher
```

#### modal.container_process

Represents a running process inside a container. Communicates via direct worker connection.

### Configuration

#### modal.config

Minimal configuration — mainly API tokens (token_id, token_secret).

**Configuration sources (priority order):**
1. Environment variables: `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
2. `.modal.toml` in home directory:

```toml
[default]
token_id = "ak-..."
token_secret = "as-..."
```

**Other config options (in .modal.toml):**

```toml
[default]
server_url = "https://api.modal.com"  # Custom server URL
```


## Reference Files

Detailed documentation for each topic:

- `references/getting-started.md` — Installation, authentication, first app
- `references/functions.md` — Functions, classes, lifecycle hooks, remote execution
- `references/images.md` — Container images, package installation, caching
- `references/gpu.md` — GPU types, selection, multi-GPU, training
- `references/volumes.md` — Persistent storage, file management, v2 volumes
- `references/secrets.md` — Credentials, environment variables, dotenv
- `references/web-endpoints.md` — FastAPI, ASGI/WSGI, streaming, auth, WebSockets
- `references/scheduled-jobs.md` — Cron, periodic schedules, management
- `references/scaling.md` — Autoscaling, concurrency, .map(), limits
- `references/resources.md` — CPU, memory, disk, timeout configuration
- `references/examples.md` — Common use cases and patterns
- `references/api_reference.md` — Key API classes and methods

Read these files when detailed information is needed beyond this overview.
