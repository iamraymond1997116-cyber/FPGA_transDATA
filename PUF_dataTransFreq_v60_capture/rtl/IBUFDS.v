`timescale 1ns / 1ps

module IBUFDS #(
    parameter DIFF_TERM = "FALSE",
    parameter IBUF_LOW_PWR = "TRUE",
    parameter IOSTANDARD = "default"
) (
    output wire O,
    input  wire I,
    input  wire IB
);

    assign O = I;

endmodule

