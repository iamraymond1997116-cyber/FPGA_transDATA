`timescale 1ns / 1ps

module uart_tx #(
    parameter integer CLKS_PER_BIT = 10
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        txd,
    output reg        busy
);
    reg [15:0] baud_counter = 16'd0;
    reg [3:0]  bit_index = 4'd0;
    reg [9:0]  shift_reg = 10'h3ff;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            baud_counter <= 16'd0;
            bit_index <= 4'd0;
            shift_reg <= 10'h3ff;
            txd <= 1'b1;
            busy <= 1'b0;
        end else if (!busy) begin
            txd <= 1'b1;
            baud_counter <= 16'd0;
            bit_index <= 4'd0;
            if (tx_start) begin
                shift_reg <= {1'b1, tx_data, 1'b0};
                txd <= 1'b0;
                busy <= 1'b1;
            end
        end else begin
            if (baud_counter == CLKS_PER_BIT - 1) begin
                baud_counter <= 16'd0;
                if (bit_index == 4'd9) begin
                    busy <= 1'b0;
                    bit_index <= 4'd0;
                    txd <= 1'b1;
                end else begin
                    bit_index <= bit_index + 4'd1;
                    shift_reg <= {1'b1, shift_reg[9:1]};
                    txd <= shift_reg[1];
                end
            end else begin
                baud_counter <= baud_counter + 16'd1;
            end
        end
    end
endmodule
