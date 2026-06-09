`timescale 1ns / 1ps

module transient_capture #(
    parameter integer CAPTURE_COUNT = 128
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        adc_valid,
    input  wire signed [15:0] adc_ch1,
    input  wire signed [15:0] adc_ch2,
    input  wire        trigger,
    output reg         capture_done,
    output reg  [6:0]  buffer_addr,
    output wire signed [15:0] buffer_ch1_data,
    output wire signed [15:0] buffer_ch2_data,
    output reg         buffer_we
);

    reg [1:0] state;
    localparam IDLE    = 2'd0;
    localparam CAPTURE = 2'd1;
    localparam DONE    = 2'd2;

    reg [6:0] sample_cnt;
    reg signed [15:0] ch1_sample_reg;
    reg signed [15:0] ch2_sample_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            sample_cnt <= 7'd0;
            capture_done <= 1'b0;
            buffer_addr <= 7'd0;
            buffer_we <= 1'b0;
            ch1_sample_reg <= 16'sd0;
            ch2_sample_reg <= 16'sd0;
        end else begin
            capture_done <= 1'b0;
            buffer_we <= 1'b0;
            buffer_addr <= sample_cnt;

            case (state)
                IDLE: begin
                    sample_cnt <= 7'd0;
                    if (trigger) begin
                        state <= CAPTURE;
                    end
                end

                CAPTURE: begin
                    if (adc_valid) begin
                        ch1_sample_reg <= adc_ch1;
                        ch2_sample_reg <= adc_ch2;
                        buffer_we <= 1'b1;
                        if (sample_cnt == CAPTURE_COUNT - 1) begin
                            sample_cnt <= 7'd0;
                            state <= DONE;
                        end else begin
                            sample_cnt <= sample_cnt + 7'd1;
                        end
                    end
                end

                DONE: begin
                    capture_done <= 1'b1;
                    // trigger (power_on_pulse) is normally 0 by this point;
                    // fast re-trigger path reserved for future use
                    if (trigger) begin
                        state <= CAPTURE;
                    end else begin
                        state <= IDLE;
                    end
                end

                default: begin
                    state <= IDLE;
                end
            endcase
        end
    end

    assign buffer_ch1_data = ch1_sample_reg;
    assign buffer_ch2_data = ch2_sample_reg;

endmodule

