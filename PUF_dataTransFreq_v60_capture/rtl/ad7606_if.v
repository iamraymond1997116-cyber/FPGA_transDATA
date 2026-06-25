`timescale 1ns / 1ps

module ad7606_if #(
    parameter integer RESET_CYCLES     = 16'hffff,
    parameter integer IDLE_CYCLES      = 0,
    parameter integer CONV_LOW_CYCLES  = 1,
    parameter integer POST_CONV_CYCLES = 0,
    parameter integer RD_LOW_CYCLES    = 1
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        soft_rst_n,   // 运行时软复位：拉低 ≥ 50ns 触发 ADC RESET（修复 +2V DC 偏置稳态）
    input  wire [15:0] ad_data,
    input  wire        ad_busy,
    input  wire        first_data,
    output wire [2:0]  ad_os,
    output reg         ad_cs,
    output reg         ad_rd,
    output reg         ad_reset,
    output reg         ad_convstab,
    output wire        ad_data_valid,
    output reg  [15:0] ad_ch1,
    output reg  [15:0] ad_ch2,
    output reg  [15:0] ad_ch3,
    output reg  [15:0] ad_ch4,
    output reg  [15:0] ad_ch5,
    output reg  [15:0] ad_ch6,
    output reg  [15:0] ad_ch7,
    output reg  [15:0] ad_ch8
);
    localparam [3:0] IDLE      = 4'd0;
    localparam [3:0] AD_CONV   = 4'd1;
    localparam [3:0] WAIT_1    = 4'd2;
    localparam [3:0] WAIT_BUSY = 4'd3;
    localparam [3:0] READ_CH1  = 4'd4;
    localparam [3:0] READ_CH2  = 4'd5;
    localparam [3:0] READ_CH3  = 4'd6;
    localparam [3:0] READ_CH4  = 4'd7;
    localparam [3:0] READ_CH5  = 4'd8;
    localparam [3:0] READ_CH6  = 4'd9;
    localparam [3:0] READ_CH7  = 4'd10;
    localparam [3:0] READ_CH8  = 4'd11;
    localparam [3:0] READ_DONE = 4'd12;

    reg [15:0] rst_cnt;
    reg [7:0]  cycle_count;
    reg [3:0]  state;
    wire unused_first_data;

    assign ad_os = 3'b000;
    assign ad_data_valid = (state == READ_DONE);
    assign unused_first_data = first_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rst_cnt <= 16'd0;
            ad_reset <= 1'b0;
        end else if (!soft_rst_n) begin
            // 软复位触发：rst_cnt 回零，重新走一遍 RESET 序列
            rst_cnt <= 16'd0;
            ad_reset <= 1'b1;
        end else if (rst_cnt < RESET_CYCLES[15:0]) begin
            rst_cnt <= rst_cnt + 16'd1;
            ad_reset <= 1'b1;
        end else begin
            ad_reset <= 1'b0;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            cycle_count <= 8'd0;
            ad_ch1 <= 16'd0;
            ad_ch2 <= 16'd0;
            ad_ch3 <= 16'd0;
            ad_ch4 <= 16'd0;
            ad_ch5 <= 16'd0;
            ad_ch6 <= 16'd0;
            ad_ch7 <= 16'd0;
            ad_ch8 <= 16'd0;
            ad_cs <= 1'b1;
            ad_rd <= 1'b1;
            ad_convstab <= 1'b1;
        end else if (ad_reset) begin
            state <= IDLE;
            cycle_count <= 8'd0;
            ad_ch1 <= 16'd0;
            ad_ch2 <= 16'd0;
            ad_ch3 <= 16'd0;
            ad_ch4 <= 16'd0;
            ad_ch5 <= 16'd0;
            ad_ch6 <= 16'd0;
            ad_ch7 <= 16'd0;
            ad_ch8 <= 16'd0;
            ad_cs <= 1'b1;
            ad_rd <= 1'b1;
            ad_convstab <= 1'b1;
        end else begin
            case (state)
                IDLE: begin
                    ad_cs <= 1'b1;
                    ad_rd <= 1'b1;
                    ad_convstab <= 1'b1;
                    if (cycle_count == IDLE_CYCLES[7:0]) begin
                        cycle_count <= 8'd0;
                        state <= AD_CONV;
                    end else begin
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                AD_CONV: begin
                    ad_convstab <= 1'b0;
                    if (cycle_count == CONV_LOW_CYCLES[7:0]) begin
                        cycle_count <= 8'd0;
                        ad_convstab <= 1'b1;
                        state <= WAIT_1;
                    end else begin
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                WAIT_1: begin
                    if (cycle_count == POST_CONV_CYCLES[7:0]) begin
                        cycle_count <= 8'd0;
                        state <= WAIT_BUSY;
                    end else begin
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                WAIT_BUSY: begin
                    if (!ad_busy) begin
                        cycle_count <= 8'd0;
                        state <= READ_CH1;
                    end
                end
                READ_CH1: begin
                    ad_cs <= 1'b0;
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch1 <= ad_data;
                        state <= READ_CH2;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH2: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch2 <= ad_data;
                        state <= READ_CH3;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH3: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch3 <= ad_data;
                        state <= READ_CH4;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH4: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch4 <= ad_data;
                        state <= READ_CH5;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH5: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch5 <= ad_data;
                        state <= READ_CH6;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH6: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch6 <= ad_data;
                        state <= READ_CH7;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH7: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch7 <= ad_data;
                        state <= READ_CH8;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_CH8: begin
                    if (cycle_count == RD_LOW_CYCLES[7:0]) begin
                        ad_rd <= 1'b1;
                        cycle_count <= 8'd0;
                        ad_ch8 <= ad_data;
                        state <= READ_DONE;
                    end else begin
                        ad_rd <= 1'b0;
                        cycle_count <= cycle_count + 8'd1;
                    end
                end
                READ_DONE: begin
                    state <= IDLE;
                end
            endcase
        end
    end

endmodule

