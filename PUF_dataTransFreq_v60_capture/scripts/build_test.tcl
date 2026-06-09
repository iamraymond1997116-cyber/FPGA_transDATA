set project_root [file normalize [file join [file dirname [info script]] ..]]
set build_dir [file join $project_root build]
file mkdir $build_dir
cd $build_dir
set_part xc7a200tfbg484-2

# Minimal build: only what uart_tx test needs
# Skip IBUFDS.v — Vivado uses built-in unisim for correct differential clock
# read_verilog [file join $project_root rtl IBUFDS.v]
read_verilog [file join $project_root rtl pixel_clock_divider.v]
read_verilog [file join $project_root rtl uart_tx.v]
read_verilog [file join $project_root rtl capture_uart_streamer.v]
read_verilog [file join $project_root sim tb_v60_top_test.v]
# Pin constraints needed before synthesis
read_xdc [file join $project_root constraints transient_puf_v60.xdc]
set_param general.maxThreads 16
synth_design -top transient_puf_v60_top -part xc7a200tfbg484-2
# Clock constraint after synthesis
create_clock -period 5.000 [get_ports sys_clk_p]
opt_design
place_design
route_design
report_timing_summary -file [file join $build_dir timing_summary.rpt]
write_checkpoint -force [file join $build_dir transient_puf_v60_top_routed.dcp]
write_bitstream -force [file join $build_dir transient_puf_v60_top.bit]
puts "Bitstream generated: [file join $build_dir transient_puf_v60_top.bit]"
exit
