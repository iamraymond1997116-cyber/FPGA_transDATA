set script_dir [file normalize [file dirname [info script]]]
set project_root [file normalize [file join $script_dir ..]]
set bitstream [file join $project_root build transient_puf_v60_top.bit]

if {![file exists $bitstream]} {
    puts "Bitstream not found: $bitstream"
    exit 1
}

open_hw_manager
connect_hw_server
set hw_target [lindex [get_hw_targets] 0]
if {$hw_target eq ""} {
    puts "No hardware target found."
    exit 1
}
open_hw_target $hw_target

set device [lindex [get_hw_devices] 0]
if {$device eq ""} {
    puts "No hardware device found."
    exit 1
}

current_hw_device $device
refresh_hw_device -update_hw_probes false $device
set_property PROGRAM.FILE $bitstream $device
program_hw_devices $device
refresh_hw_device $device

puts "Programming complete: $bitstream"
close_hw_manager
exit
