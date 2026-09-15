# Mounting Volumes

Kale pipelines can mount Kubernetes Persistent Volume Claims (PVCs) into
pipeline steps. This is useful for:

- Sharing large datasets across steps without marshalling overhead
- Persisting outputs beyond the pipeline run
- Accessing pre-existing data stored on cluster volumes

## Adding Volumes via the JupyterLab Extension

1. Open the Kale panel in the left sidebar
2. Scroll to the **Volumes** section
3. Click **Add Volume**
4. Select a PVC from the dropdown (or type a name manually)
5. Specify the **mount path** (e.g., `/data`)
6. Optionally enable **Expose as env var** to create an environment variable
   pointing to the mount path

### Selecting from Notebook Pod

If you're running JupyterLab inside a Kubeflow notebook server, click
**Select from notebook** to see volumes already mounted on your notebook pod.
This makes it easy to use the same volumes in your pipeline.

### Access Mode Badges

Each PVC in the dropdown shows its access mode:

| Badge | Access Mode       | Description                                      |
|-------|-------------------|--------------------------------------------------|
| RWO   | ReadWriteOnce     | Can be mounted read-write by a single node       |
| RWX   | ReadWriteMany     | Can be mounted read-write by multiple nodes      |
| ROX   | ReadOnlyMany      | Can be mounted read-only by multiple nodes       |
| RWOP  | ReadWriteOncePod  | Can be mounted read-write by a single pod        |

## Volume Configuration in Notebook Metadata

Volumes are stored in the notebook's Kale metadata under the `volumes` key:

```json
{
  "kubeflow_notebook": {
    "volumes": [
      {
        "name": "my-data-pvc",
        "mount_point": "/data",
        "type": "pvc",
        "expose_as_env_var": true
      }
    ]
  }
}
```

### Fields

| Field              | Required | Description                                           |
|--------------------|----------|-------------------------------------------------------|
| `name`             | Yes      | Name of the PVC to mount                              |
| `mount_point`      | Yes      | Absolute path where the volume will be mounted        |
| `type`             | Yes      | Always `"pvc"` for PVC volumes                        |
| `expose_as_env_var`| No       | If `true`, creates `KALE_VOLUME_<NAME>` env var       |

## Environment Variables

When `expose_as_env_var` is enabled, Kale creates an environment variable in
each pipeline step container. The variable name is derived from the PVC name:

- PVC name: `my-data-pvc`
- Env var: `KALE_VOLUME_MY_DATA_PVC`
- Value: `/data` (the mount path)

This lets your code reference the mount path without hardcoding it:

```python
import os

data_path = os.environ["KALE_VOLUME_MY_DATA_PVC"]
df = pd.read_parquet(f"{data_path}/dataset.parquet")
```

## ReadWriteOnce / ReadWriteOncePod Warning

When you compile or run a pipeline with **ReadWriteOnce (RWO)** or
**ReadWriteOncePod (RWOP)** volumes, Kale shows a warning dialog:

> Pipeline has RWO mounted volumes.
>
> Parallel steps may fail if scheduled on different nodes. Consider using
> ReadWriteMany volumes for parallel pipelines.

### Why This Matters

These access modes have mounting restrictions that can cause pipeline failures:

| Access Mode       | Restriction                                           |
|-------------------|-------------------------------------------------------|
| ReadWriteOnce     | Can only be mounted by pods on the **same node**      |
| ReadWriteOncePod  | Can only be mounted by a **single pod** at a time     |

If your pipeline has parallel steps (steps that don't depend on each other):
- **RWO**: Kubernetes may schedule steps on different nodes, and some will fail
  to mount the volume.
- **RWOP**: Only one step pod can mount the volume at a time, so parallel steps
  will fail or hang waiting for the volume.

### Solutions

1. **Use ReadWriteMany (RWX) volumes** — These can be mounted by pods on any
   node simultaneously. Most network file systems (NFS, CephFS, etc.) support RWX.

2. **Ensure sequential execution** — If all steps depend on each other (no
   parallelism), they'll run one at a time and the RWO/RWOP limitation won't apply.

3. **Use node affinity** — Configure your Kubeflow cluster to schedule all
   pipeline pods on the same node (advanced, not recommended for most cases).
   Note: This only helps with RWO, not RWOP.

## Best Practices

1. **Use RWX for parallel pipelines** — If your pipeline has any parallel
   branches, prefer ReadWriteMany volumes to avoid scheduling conflicts.
   Avoid RWO (node-restricted) and RWOP (single-pod) access modes.

2. **Mount read-only when possible** — If steps only read from a volume,
   consider using ReadOnlyMany (ROX) access mode for safety.

3. **Use env vars for portability** — Enable `expose_as_env_var` so your code
   doesn't hardcode mount paths. This makes notebooks easier to reconfigure.

4. **Keep mount paths simple** — Use short, descriptive paths like `/data`,
   `/models`, or `/output`. Avoid paths with spaces or special characters.

5. **Check PVC existence** — Kale validates that PVCs exist when you add them
   via the UI, but if you edit metadata directly, ensure the PVC exists in
   the target namespace before running the pipeline.
