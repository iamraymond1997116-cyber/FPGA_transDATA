// ============================================================================
// capture_uart_streamer — UART ASCII frame output for V6.x multi-mode capture
//
// Frame format (29 bytes header + CH1/CH2 raw 128×4-hex + \n):
//   V6.0,MODE=XXXX,SPWR=X,TXN=XX\n
//   CH1,RAW,128,...\n
//   CH2,RAW,128,...\n
//
// Mode names (4-char):
//   FULL — MODE_FULL         : ON@0, OFF@64
//   PCUT — MODE_POS_CUT      : ON@0, OFF@8
//   NCUT — MODE_NEG_CUT      : OFF@0, ON@9
//   EXTR — MODE_EXTREMA_CYCLE: alternating ON(8)/OFF(9)
//   FCYC — MODE_FULL_CYCLE   : ON→OFF@32, ON@64, OFF@96
//
// Handshake: TX → WAIT_ACK(busy=1) → return → WAIT_IDLE(busy=0) → next byte
// ============================================================================
`timescale 1ns / 1ps

module capture_uart_streamer #(
    parameter integer CLKS_PER_BIT = 9,
    parameter [7:0] VERSION_MAJOR = 8'd6,
    parameter [7:0] VERSION_MINOR = 8'd1
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        send,
    input  wire [2:0]  mode,
    input  wire [7:0]  txn_id,
    input  wire        sensor_power,
    input  wire signed [15:0] raw_ch1_data,
    input  wire signed [15:0] raw_ch2_data,
    output reg  [6:0]  raw_addr,
    output wire        txd,
    output wire        busy
);

    localparam [3:0] ST_IDLE       = 4'd0;
    localparam [3:0] ST_HDR        = 4'd1;
    localparam [3:0] ST_PREFIX     = 4'd2;
    localparam [3:0] ST_LATCH_ADDR = 4'd3;  // set BRAM address
    localparam [3:0] ST_SAMPLE     = 4'd4;
    localparam [3:0] ST_WAIT_ACK   = 4'd5;
    localparam [3:0] ST_DONE       = 4'd7;
    localparam [3:0] ST_LATCH_DATA = 4'd8;  // capture BRAM data (1 cycle after addr)

    reg [3:0] state = ST_IDLE;
    reg [3:0] return_state = ST_IDLE;
    reg [7:0] idx = 8'd0;
    reg [6:0] sample_idx = 7'd0;
    reg [2:0] nibble_idx = 3'd0;
    reg [7:0] tx_data_reg = 8'd0;
    reg tx_start = 1'b0;
    reg channel_sel = 1'b0;
    reg [15:0] sample_latch = 16'sd0;
    wire tx_busy;

    // 4-char mode name lookup (function for header generation)
    function [31:0] mode_name;
        input [2:0] m;
        begin
            case (m)
                3'd0: mode_name = "FULL";
                3'd1: mode_name = "PCUT";
                3'd2: mode_name = "NCUT";
                3'd3: mode_name = "EXTR";
                3'd4: mode_name = "FCYC";
                default: mode_name = "UNKN";
            endcase
        end
    endfunction

    // Pre-computed mode name bytes for header use (Verilator can't part-select function return)
    wire [7:0] mode_b3, mode_b2, mode_b1, mode_b0;
    assign {mode_b3, mode_b2, mode_b1, mode_b0} = mode_name(mode);

    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (
        .clk(clk),
        .rst_n(rst_n),
        .tx_start(tx_start),
        .tx_data(tx_data_reg),
        .txd(txd),
        .busy(tx_busy)
    );

    assign busy = (state != ST_IDLE) || tx_busy;

    function [7:0] hex_digit;
        input [3:0] val;
        begin
            hex_digit = (val < 10) ? (8'd48 + val) : (8'd55 + val);
        end
    endfunction

    function [7:0] nibble_char;
        input [15:0] value;
        input [1:0] pos;
        begin
            case (pos)
                2'd0: nibble_char = hex_digit(value[15:12]);
                2'd1: nibble_char = hex_digit(value[11:8]);
                2'd2: nibble_char = hex_digit(value[7:4]);
                default: nibble_char = hex_digit(value[3:0]);
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= ST_IDLE;
            return_state <= ST_IDLE;
            idx <= 8'd0;
            sample_idx <= 7'd0;
            nibble_idx <= 3'd0;
            raw_addr <= 7'd0;
            tx_data_reg <= 8'd0;
            tx_start <= 1'b0;
            channel_sel <= 1'b0;
            sample_latch <= 16'sd0;
        end else begin
            tx_start <= 1'b0;

            case (state)

                ST_IDLE: begin
                    if (send) begin
                        idx <= 8'd0;
                        sample_idx <= 7'd0;
                        nibble_idx <= 3'd0;
                        raw_addr <= 7'd0;
                        channel_sel <= 1'b0;
                        state <= ST_HDR;
                    end
                end

                // ── Header: V6.0,MODE=XXXX,SPWR=X,TXN=XX\n ──
                ST_HDR: begin
                    if (!tx_busy) begin
                        // header layout (29 bytes total):
                        //  0 1 2 3 4  5 6 7 8  9 10 11 12  13 14 15 16  17 18 19 20 21 22 23 24 25 26 27 28
                        //  V 6 . 0 ,  M O D E  =  M  M  M  M   ,  S  P  W  R  =  X  ,  T  X  N  =  X  X  \n
                        case (idx)
                            // V + MAJOR + . + MINOR (dynamic from parameters)
                            8'd0:  tx_data_reg <= "V";
                            8'd1:  tx_data_reg <= 8'd48 + VERSION_MAJOR[3:0];
                            8'd2:  tx_data_reg <= ".";
                            8'd3:  tx_data_reg <= 8'd48 + VERSION_MINOR[3:0];
                            8'd4:  tx_data_reg <= ",";
                            8'd5:  tx_data_reg <= "M";
                            8'd6:  tx_data_reg <= "O";
                            8'd7:  tx_data_reg <= "D";
                            8'd8:  tx_data_reg <= "E";
                            8'd9:  tx_data_reg <= "=";
                            // idx 10-13: mode name (4 bytes)
                            8'd10: tx_data_reg <= mode_b3;
                            8'd11: tx_data_reg <= mode_b2;
                            8'd12: tx_data_reg <= mode_b1;
                            8'd13: tx_data_reg <= mode_b0;
                            8'd14: tx_data_reg <= ",";
                            8'd15: tx_data_reg <= "S";
                            8'd16: tx_data_reg <= "P";
                            8'd17: tx_data_reg <= "W";
                            8'd18: tx_data_reg <= "R";
                            8'd19: tx_data_reg <= "=";
                            8'd20: tx_data_reg <= sensor_power ? "1" : "0";
                            8'd21: tx_data_reg <= ",";
                            8'd22: tx_data_reg <= "T";
                            8'd23: tx_data_reg <= "X";
                            8'd24: tx_data_reg <= "N";
                            8'd25: tx_data_reg <= "=";
                            8'd26: tx_data_reg <= hex_digit(txn_id[7:4]);
                            8'd27: tx_data_reg <= hex_digit(txn_id[3:0]);
                            8'd28: tx_data_reg <= 8'h0A;
                            default: tx_data_reg <= 8'h0A;
                        endcase
                        tx_start <= 1'b1;
                        return_state <= ST_HDR;
                        state <= ST_WAIT_ACK;
                        if (idx == 8'd28) begin
                            idx <= 8'd0;
                            return_state <= ST_PREFIX;
                            state <= ST_WAIT_ACK;
                        end else begin
                            idx <= idx + 8'd1;
                        end
                    end
                end

                // ── CH1/CH2 Prefix: CH1,RAW,128, ──
                ST_PREFIX: begin
                    if (!tx_busy) begin
                        case (idx)
                            8'd0:  tx_data_reg <= "C";
                            8'd1:  tx_data_reg <= "H";
                            8'd2:  tx_data_reg <= channel_sel ? "2" : "1";
                            8'd3:  tx_data_reg <= ",";
                            8'd4:  tx_data_reg <= "R";
                            8'd5:  tx_data_reg <= "A";
                            8'd6:  tx_data_reg <= "W";
                            8'd7:  tx_data_reg <= ",";
                            8'd8:  tx_data_reg <= "1";
                            8'd9:  tx_data_reg <= "2";
                            8'd10: tx_data_reg <= "8";
                            8'd11: tx_data_reg <= ",";
                            default: tx_data_reg <= 8'h0A;
                        endcase
                        tx_start <= 1'b1;
                        return_state <= ST_PREFIX;
                        state <= ST_WAIT_ACK;
                        if (idx == 8'd11) begin
                            idx <= 8'd0;
                            return_state <= ST_LATCH_ADDR;
                            state <= ST_WAIT_ACK;
                        end else begin
                            idx <= idx + 8'd1;
                        end
                    end
                end

                // ── Set BRAM address (1 cycle before data capture) ──
                ST_LATCH_ADDR: begin
                    raw_addr <= sample_idx;
                    state <= ST_LATCH_DATA;
                end

                // ── Capture BRAM data (address stabilised from previous cycle) ──
                ST_LATCH_DATA: begin
                    if (channel_sel == 1'b0)
                        sample_latch <= raw_ch1_data;
                    else
                        sample_latch <= raw_ch2_data;
                    nibble_idx <= 3'd0;
                    state <= ST_SAMPLE;
                end

                // ── Output 4 hex nibbles ──
                ST_SAMPLE: begin
                    if (!tx_busy) begin
                        if (nibble_idx < 3'd4) begin
                            tx_data_reg <= nibble_char(sample_latch, nibble_idx[1:0]);
                            tx_start <= 1'b1;
                            return_state <= ST_SAMPLE;
                            state <= ST_WAIT_ACK;
                            nibble_idx <= nibble_idx + 3'd1;
                        end else begin
                            // All 4 nibbles sent
                            if (sample_idx == 7'd127) begin
                                // Last sample → newline and done with channel
                                tx_data_reg <= 8'h0A;
                                tx_start <= 1'b1;
                                sample_idx <= 7'd0;
                                nibble_idx <= 3'd0;
                                if (channel_sel == 1'b0) begin
                                    // CH1 done → do CH2
                                    channel_sel <= 1'b1;
                                    return_state <= ST_PREFIX;
                                end else begin
                                    // CH2 done → all done
                                    return_state <= ST_DONE;
                                end
                                state <= ST_WAIT_ACK;
                            end else begin
                                // Not last sample → comma separator
                                tx_data_reg <= 8'h2C;
                                tx_start <= 1'b1;
                                return_state <= ST_LATCH_ADDR;
                                state <= ST_WAIT_ACK;
                                sample_idx <= sample_idx + 7'd1;
                                nibble_idx <= 3'd0;
                            end
                        end
                    end
                end

                // ── Wait for uart_tx to acknowledge (tx_busy=1) ──
                ST_WAIT_ACK: begin
                    if (tx_busy)
                        state <= return_state;
                end

                ST_DONE: begin
                    state <= ST_IDLE;
                end

                default: begin
                    state <= ST_IDLE;
                    idx <= 8'd0;
                    sample_idx <= 7'd0;
                    nibble_idx <= 3'd0;
                    raw_addr <= 7'd0;
                    channel_sel <= 1'b0;
                end
            endcase
        end
    end

endmodule
