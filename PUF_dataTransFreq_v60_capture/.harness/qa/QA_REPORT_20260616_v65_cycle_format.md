# QA Report — V6.5 cycle-format patch

## Scope
- Add explicit sample_id/SID and mode_idx/MID to UART frames.
- Increment sample_id only after FCYC completes, so FULL/PCUT/NCUT/EXTR/FCYC share one sample ID.
- Update PC capture parser and add post_process.py to generate X_cycles.npz with shape [N,5,2,128].

## Verification performed in sandbox
- `python3 scripts/capture_ascii_v60.py --test` → PASS.
- `python3 -m py_compile scripts/capture_ascii_v60.py scripts/post_process.py` → PASS.

## Not run in sandbox
- `.\.harness\tasks.ps1 check` was not run here because the sandbox is Linux and the harness requires Windows PowerShell/Vivado/Verilator paths from the project machine.

## Follow-up on hardware workstation
1. `.\.harness\tasks.ps1 check`
2. `.\.harness\tasks.ps1 build`
3. `.\.harness\tasks.ps1 program`
4. `.\.harness\tasks.ps1 capture -Port COM5 --samples 10`
