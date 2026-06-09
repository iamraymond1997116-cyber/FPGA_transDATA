# Simulation

Minimal capture testbenches go here.

Current focus:
- `tb_trigger_chain.v`: trigger chain and capture count
- `tb_uart_ascii_stream.sv`: ASCII UART frame sanity check

Current verification focus:
- `tb_trigger_chain.sv` / `tb_trigger_chain.v`
- prove `capture_start -> power_on_pulse -> capture_done`
- keep the simulation short and single-purpose
