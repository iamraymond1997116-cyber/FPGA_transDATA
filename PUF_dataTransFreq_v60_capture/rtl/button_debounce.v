`timescale 1ns / 1ps

module button_debounce #(
    parameter integer DEBOUNCE_CYCLES = 4000000
) (
    input  wire clk,
    input  wire noisy,
    output reg  stable = 1'b0,
    output reg  press_pulse = 1'b0
);
    localparam integer COUNTER_WIDTH = (DEBOUNCE_CYCLES <= 1) ? 1 : $clog2(DEBOUNCE_CYCLES);

    reg sync_ff0 = 1'b0;
    reg sync_ff1 = 1'b0;
    reg [COUNTER_WIDTH-1:0] counter = {COUNTER_WIDTH{1'b0}};

    always @(posedge clk) begin
        sync_ff0 <= noisy;
        sync_ff1 <= sync_ff0;
        press_pulse <= 1'b0;

        if (sync_ff1 == stable) begin
            counter <= {COUNTER_WIDTH{1'b0}};
        end else if (counter == DEBOUNCE_CYCLES - 1) begin
            stable <= sync_ff1;
            press_pulse <= sync_ff1;
            counter <= {COUNTER_WIDTH{1'b0}};
        end else begin
            counter <= counter + 1'b1;
        end
    end
endmodule

