
# OSC Streaming Manifest (Rokoko → Unreal Control Rig)

- **Transport:** UDP / OSC
- **Target:** 127.0.0.1:7000
- **Rate:** 60 Hz (use CSV timestamp or real time while streaming live)
- **Units:** degrees (no normalization)
- **Address convention:** `/bone/{bone}/{axis}` with one float payload

Axes mapping:
- `pitch` = flexion/extension (rotate around X)
- `roll`  = lateral tilt / adduction-abduction (rotate around Z)
- `yaw`   = axial / internal-external rotation (rotate around Y)

### How to stream
For each row `t` in the Rokoko CSV:
1. For each route in `osc_mapping.json`:
   - Read `source_column` value.
   - Apply `transform.scale * value + transform.offset`, then clamp if provided.
   - Send OSC message to `osc_address` with the float.

### Unreal side
- Use the **OSC plugin**.
- Bind address patterns like `/bone/*/pitch`, `/bone/*/roll`, `/bone/*/yaw`.
- For each message:
  - Parse `bone` and `axis` from the address string.
  - Route to **Control Rig**:
    - Either call `Set Bone Rotation` directly on that bone, or
    - Expose a matching **Float Control** per axis (e.g., `hand_r_pitch`) and set it.

### Spine distribution
Thorax rotation signals are distributed across `spine_01..spine_05` using weights `[0.10, 0.20, 0.30, 0.25, 0.15]`. Adjust in `osc_mapping.json` if your rig prefers different weighting.

### Optional smoothing
Add an EMA per channel in the Python sender:
`y_t = alpha * x_t + (1-alpha) * y_{t-1}` with `alpha≈0.3` for 60 Hz.

