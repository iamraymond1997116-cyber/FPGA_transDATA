set script_dir [file normalize [file dirname [info script]]]
set project_root [file normalize [file join $script_dir ..]]
set build_dir [file join $project_root build]

file mkdir $build_dir
cd $build_dir

set_part xc7a200tfbg484-2

# Skip IBUFDS.v — Vivado uses built-in unisim for correct differential clock
# (Stub is for Verilator lint only)
# read_verilog [file join $project_root rtl IBUFDS.v]
read_verilog [file join $project_root rtl pixel_clock_divider.v]
read_verilog [file join $project_root rtl button_debounce.v]
read_verilog [file join $project_root rtl ad7606_if.v]
read_verilog [file join $project_root rtl sensor_power_control.v]
read_verilog [file join $project_root rtl transient_capture.v]
read_verilog [file join $project_root rtl uart_tx.v]
read_verilog [file join $project_root rtl capture_uart_streamer.v]
read_verilog [file join $project_root rtl lcd_timing.v]
read_verilog [file join $project_root rtl lcd_version_mode_display.v]
read_verilog [file join $project_root rtl mini_font_rom.v]
read_verilog [file join $project_root rtl transient_puf_v60_top.v]

read_xdc [file join $project_root constraints transient_puf_v60.xdc]

set_param general.maxThreads 16
synth_design -top transient_puf_v60_top -part xc7a200tfbg484-2
opt_design
place_design
route_design

set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]

report_timing_summary -file [file join $build_dir timing_summary.rpt]
report_utilization -file [file join $build_dir utilization.rpt]

write_checkpoint -force [file join $build_dir transient_puf_v60_top_routed.dcp]
write_bitstream -force [file join $build_dir transient_puf_v60_top.bit]

puts "Bitstream generated: [file join $build_dir transient_puf_v60_top.bit]"
exit
