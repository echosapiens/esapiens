# Modal API Reference (Full)

## Core Classes

### modal.App

The main unit of deployment. Groups related functions and classes together.

```python
app = modal.App("my-app")
app = modal.App("my-app", tags={"team": "ml", "project": "inference"})
```

**Decorators:**
- `@app.function(**kwargs)` — Register a serverless function
- `@app.cls(**kwargs)` — Register a stateful class
- `@app.local_entrypoint()` — Mark as local entry point

**Methods:**
- `.deploy(name)` — Deploy to production
- `.spawn(name)` — Create new app instance
- `.stop()` — Stop all containers
- `.get_function(name)`/`.get_cls(name)` — Get registered objects

### modal.Function

The basic unit of serverless execution. Created via `@app.function()`.

**Parameters:** image, gpu, cpu, memory, ephemeral_disk, timeout, secrets, volumes, schedule, max_containers, min_containers, buffer_containers, scaledown_window, retries, name, cloud, region

**Execution methods:**
- `.remote(*args)` — Cloud execution (sync)
- `.spawn(*args)` — Cloud execution (async, returns FunctionCall)
- `.local(*args)` — Local execution
- `.map(inputs)` — Parallel over iterable
- `.starmap(inputs)` — Parallel with tuple args
- `.for_each(inputs)` — Fire-and-forget parallel
- `.from_name(app, fn)` — Reference deployed function
- `.update_autoscaler(**kwargs)` — Dynamic scaling

### modal.FunctionCall

A handle to an async function call (from `.spawn()`).
- `.get(timeout)` — Block for result
- `.get_call_id()` — Unique call ID
- `.cancel()` — Cancel the call

### modal.Cls

Stateful class with lifecycle hooks. Use `@app.cls()`.

**Decorators:**
- `@modal.enter()` — On container start
- `@modal.exit()` — On container shutdown
- `@modal.method()` — Expose as callable
- `@modal.parameter()` — Class parameter (like dataclass.field)

**Usage:** `MyClass().method.remote(args)`

### modal.Image

Container image definition. Factory methods: `debian_slim()`, `from_registry()`, `from_dockerfile()`, `micromamba()`

**Builder methods:** `.uv_pip_install()`, `.pip_install()`, `.apt_install()`, `.run_commands()`, `.run_function()`, `.env()`, `.add_local_dir()`, `.add_local_file()`, `.add_local_python_source()`, `.copy()`, `.dockerfile_commands()`, `.imports()`

## Storage

### modal.Volume

Persistent file storage between functions. Requires explicit `.commit()` and `.reload()`.

**Methods:** `.from_name()`, `.commit()`, `.reload()`, `.rename()`, `.delete()`
**Filesystem ops:** `.objects.listdir()`, `.readfile()`, `.writefile()`, `.remove()`, `.copy()`

### modal.CloudBucketMount

Mount S3/GCS/Azure buckets. Uses S3 Mountpoint.
- `bucket_name`, `secret`, `read_only`
- Optimized for large sequential reads

### modal.NetworkFileSystem

Deprecated — use Volume instead.

### modal.Dict

Distributed key-value store (cloudpickle-serialized).
- Dict-like API: `d[key]`, `d[key]=value`, `del d[key]`, `key in d`
- Methods: `.keys()`, `.values()`, `.items()`, `.get()`, `.put()`, `.put_if_new()`, `.update()`, `.clear()`, `.len()`, `.delete()`

### modal.Queue

Distributed FIFO queue with optional partitions.
- `.put(item, partition=)`, `.get(timeout=)`, `.get_nowait()`
- `.len(partition=)`, `.peek(n=)`, `.clear(partition=)`, `.delete()`

## Security

### modal.Secret

Environment variable injection. Access via `os.environ["KEY"]`.
- `Secret.from_name(name, required_keys=[])`
- `Secret.from_dict(d)` — Dev only, not secure!
- `Secret.from_dotenv(path)`

### modal.Proxy

Static outbound IP for containers.
- `modal.Proxy.from_name("name", create_if_missing=True)`

## Scheduling

### modal.Cron

Standard cron: `modal.Cron("0 9 * * *")`. Stable across deploys.

### modal.Period

Fixed interval: `modal.Period(hours=4)`. Resets on redeploy.

## Web Endpoints

### @modal.fastapi_endpoint(method, label, docs, custom_domains, requires_proxy_auth)

Simple FastAPI endpoint for single functions.

### @modal.asgi_app(label, custom_domains)

Full ASGI app (FastAPI, Starlette, FastHTML).

### @modal.wsgi_app(label, custom_domains)

Full WSGI app (Flask, Django).

### @modal.web_server(port, startup_timeout, label, custom_domains)

Run any custom web server that binds a port.

## Function Modifiers

### @modal.concurrent(max_inputs, target_inputs)

Multiple concurrent inputs per container. Requires async functions.

### @modal.batched(max_batch_size, wait_ms)

Dynamic input batching. Stack under `@app.function()`.

## Sandbox

### modal.Sandbox

Isolated command execution in containers.

**Key parameters:** `*args`, `image`, `app`, `name`, `timeout`, `idle_timeout`, `gpu`, `cpu`, `memory`, `env`, `secrets`, `workdir`, `volumes`, `readiness_probe`, `force_build`

**Methods:** `Sandbox.create()`, `.wait()`, `.terminate()`, `.stop()`, `.exec()`, `.detach()`, `.mount_image()`, `.stdout`, `.stderr`, `.returncode`

**Probes:**
- `Probe.with_exec("sh", "-c", "test -f /tmp/ready")`
- `Probe.with_tcp(8080)`

### modal.SandboxSnapshot

[Preview] Memory/filesystem state snapshots.

### modal.forward(port)

Expose a container port publicly with TLS. Returns `Tunnel` with `.url`.

## Utilities

### modal.Client.from_credentials(token_id, token_secret)

Low-level Modal API client.

### modal.Environment

Environment management: `objects.create(name)`, `.list()`, `.delete(name)`

### modal.billing.workspace_billing_report(start, end)

Billing report generation. Returns list of report items.

### modal.call_graph.InputInfo / InputStatus

Distributed function call tracing.

### modal.Error

Base class for all Modal errors.

## Exception Classes

| Exception | Description |
|-----------|-------------|
| `modal.Error` | Base class for all Modal errors |
| `modal.exception.AuthError` | Missing or invalid authentication |
| `modal.exception.AlreadyExistsError` | Resource creation conflict |
| `modal.exception.AsyncUsageWarning` | Sync API in async context |
| `modal.exception.ClientClosed` | Client already closed |
| `modal.exception.ConnectionError` | Connection failures |
| `modal.exception.DeprecationError` | Usage of deprecated API |
| `modal.exception.InternalFailure` | Internal Modal error |
| `modal.exception.LogsFetchError` | Failed to fetch logs |
| `modal.exception.OutputExpiredError` | Function output expired |
| `modal.exception.RemoteError` | Error from remote execution |
| `modal.exception.TimeoutError` | Operation timed out |
| `modal.exception.VersionError` | Client/server version mismatch |
| `modal.exception.SandboxFilesystemDirectoryNotEmptyError` | Directory not empty |

**GRPCError migration:** As of v1.3, Modal is migrating from `grpclib.GRPCError` to Modal-specific exception types. Map:
- `NOT_FOUND` → `NotFoundError`
- `ALREADY_EXISTS` → `AlreadyExistsError`
- `PERMISSION_DENIED` → `PermissionDeniedError`
- `RESOURCE_EXHAUSTED` → `ResourceExhaustedError`
- `UNAUTHENTICATED` → `AuthError`
- `INTERNAL` → `InternalError`
- `UNAVAILABLE` / `CANCELLED` / `DEADLINE_EXCEEDED` → `ServiceError`

## GPU Reference

| GPU String | GPU | VRAM | Use Case |
|-----------|-----|------|----------|
| `"T4"` | NVIDIA T4 | 16 GB | Light inference, CI |
| `"L4"` | NVIDIA L4 | 24 GB | General inference |
| `"A10"` | NVIDIA A10 | 24 GB | General workload |
| `"L40S"` | NVIDIA L40S | 48 GB | Inference (best value) |
| `"A100-40GB"` | NVIDIA A100 | 40 GB | Training |
| `"A100-80GB"` | NVIDIA A100 | 80 GB | Large model training |
| `"H100"` | NVIDIA H100 | 80 GB | Heavy training/inference |
| `"H100!`" | H100 (pin) | 80 GB | No auto-upgrade |
| `"H200"` | NVIDIA H200 | 141 GB | Very large models |
| `"B200"` | NVIDIA B200 | 192 GB | Next-gen |
| `"B200+"` | B200/B300 | 192 GB | B200 price, B300 if avail |
| `"H100:4"` | 4x H100 | — | Distributed training |

## Config Reference

**.modal.toml** (in home directory):
```toml
[default]
token_id = "ak-..."
token_secret = "as-..."
server_url = "https://api.modal.com"
```

**Environment variables (take precedence):** `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `MODAL_ENVIRONMENT`, `MODAL_DEV_SUFFIX`

## Function Defaults

| Resource | Default | Max |
|----------|---------|-----|
| CPU cores | 0.125 | — |
| Memory | 128 MiB | — |
| Ephemeral disk | 51200 MiB (50 GB) | 3 TiB |
| Timeout | 300s | — |
| Max containers | 100 | — |
| Min containers | 0 | — |
| Scaledown window | 300s | — |
