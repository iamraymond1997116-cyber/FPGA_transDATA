set script_dir [file dirname [info script]]
set proj_dir [file normalize [file join $script_dir ..]]
set rtl_dir [file join $proj_dir rtl]
set sim_dir [file join $proj_dir sim]

puts "RTL_DIR=$rtl_dir"
puts "SIM_DIR=$sim_dir"

xvlog -sv \
    [file join $rtl_dir uart_tx.v] \
    [file join $rtl_dir capture_uart_streamer.v] \
    [file join $sim_dir tb_uart_ascii_stream.sv]

xelab tb_uart_ascii_stream -debug typical -top tb_uart_ascii_stream
xsim tb_uart_ascii_stream -runall
