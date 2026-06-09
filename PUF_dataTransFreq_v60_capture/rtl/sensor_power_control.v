// ============================================================================
// sensor_power_control — 5-mode power sequencing for V6.x transient sampling
//
// Mode encoding:
//   3'd0 = MODE_FULL         : ON@0, OFF@64, steady after 64
//   3'd1 = MODE_POS_CUT      : ON@0, OFF@8 , steady after 8
//   3'd2 = MODE_NEG_CUT      : precharge→OFF@0, ON@8, steady after 8
//   3'd3 = MODE_EXTREMA_CYCLE: fixed 8-sample phases (128/8=16 toggles)
//   3'd4 = MODE_FULL_CYCLE   : ON→OFF@32, OFF→ON@64, ON→OFF@96
//
// Sensor power: 1=OFF, 0=ON (PMOS n-channel control)
// capture_trigger fires once at the start of the sampling window.
// All edge detection uses fully-registered signals (no wire glitch races).
// ============================================================================
`timescale 1ns / 1ps

module sensor_power_control #(
    parameter integer PRECHARGE_CYCLES = 1000
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        trigger,
    input  wire [2:0]  mode,
    input  wire        sample_tick,
    input  wire        early_precharge,  // pre-assert ON during UART busy (NEG_CUT)
    output reg         sensor_power    = 1'b1,
    output reg         power_on_pulse  = 1'b0,
    output reg         power_off_pulse = 1'b0,
    output reg         capture_trigger = 1'b0
);

    localparam [1:0] ST_IDLE      = 2'd0;
    localparam [1:0] ST_PRECHARGE = 2'd1;
    localparam [1:0] ST_ACTIVE    = 2'd2;
    localparam [1:0] ST_DONE      = 2'd3;

    reg [1:0] state = ST_IDLE;
    reg [6:0] sample_cnt = 7'd0;
    reg [15:0] precharge_cnt = 16'd0;
    reg        negcut_precharged = 1'b0;  // early precharge done during IDLE

    // 2-stage trigger synchronizer — eliminates race with TB blocking assignments
    reg trigger_s1 = 1'b0;
    reg trigger_s2 = 1'b0;
    // EXTREMA_CYCLE phase tracking (fixed 7-sample phases)
    reg [3:0] phase_cnt = 4'd0;

    wire trigger_rise = trigger_s1 && !trigger_s2;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= ST_IDLE;
            sample_cnt <= 7'd0;
            precharge_cnt <= 16'd0;
            trigger_s1 <= 1'b0;
            trigger_s2 <= 1'b0;
            sensor_power <= 1'b1;
            power_on_pulse <= 1'b0;
            power_off_pulse <= 1'b0;
            capture_trigger <= 1'b0;
            phase_cnt <= 4'd0;

            negcut_precharged <= 1'b0;
        end else begin
            // ── default: de-assert single-cycle pulses ──
            power_on_pulse  <= 1'b0;
            power_off_pulse <= 1'b0;
            capture_trigger <= 1'b0;

            // 2-stage trigger synchronizer
            trigger_s2 <= trigger_s1;
            trigger_s1 <= trigger;

            case (state)

                ST_IDLE: begin
                    sample_cnt <= 7'd0;
                    precharge_cnt <= 16'd0;
                    phase_cnt <= 4'd0;
        

                    // Early precharge for NEG_CUT: turn sensor ON during UART busy
                    if (early_precharge && mode == 3'd2) begin
                        sensor_power <= 1'b0;       // ON — precharge overlaps UART
                        negcut_precharged <= 1'b1;
                    end else begin
                        sensor_power <= 1'b1;       // OFF — default idle
                        negcut_precharged <= 1'b0;
                    end

                    if (trigger_rise) begin
                        if (mode == 3'd2 && (negcut_precharged || early_precharge)) begin
                            // Precharge done (or starting now) — skip PRECHARGE
                            sensor_power <= 1'b1;   // OFF
                            power_off_pulse <= 1'b1;
                            capture_trigger <= 1'b1;
                            state <= ST_ACTIVE;
                            negcut_precharged <= 1'b0;
                        end else if (mode == 3'd2) begin
                            // Fallback: no early precharge, do it now
                            sensor_power <= 1'b0;
                            state <= ST_PRECHARGE;
                        end else begin
                            // ON-first modes
                            sensor_power <= 1'b0;
                            power_on_pulse <= 1'b1;
                            capture_trigger <= 1'b1;
                            state <= ST_ACTIVE;
                        end
                    end
                end

                ST_PRECHARGE: begin
                    // sensor_power stays 0 (ON) during precharge
                    if (precharge_cnt == PRECHARGE_CYCLES - 1) begin
                        sensor_power <= 1'b1;
                        power_off_pulse <= 1'b1;
                        capture_trigger <= 1'b1;
                        precharge_cnt <= 16'd0;
                        state <= ST_ACTIVE;
                    end else begin
                        precharge_cnt <= precharge_cnt + 16'd1;
                    end
                end

                ST_ACTIVE: begin
                    if (sample_tick) begin
                        case (mode)
                            3'd0: begin  // FULL: OFF at sample 64
                                if (sample_cnt == 7'd63) begin
                                    sensor_power <= 1'b1;
                                    power_off_pulse <= 1'b1;
                                end
                            end

                            3'd1: begin  // POS_CUT: OFF at sample 8
                                if (sample_cnt == 7'd7) begin
                                    sensor_power <= 1'b1;
                                    power_off_pulse <= 1'b1;
                                end
                            end

                            3'd2: begin  // NEG_CUT: ON at sample 8
                                if (sample_cnt == 7'd7) begin
                                    sensor_power <= 1'b0;
                                    power_on_pulse <= 1'b1;
                                end
                            end

                            3'd3: begin  // EXTREMA_CYCLE: fixed 8-sample phases
                                if (phase_cnt == 4'd7) begin
                                    sensor_power <= ~sensor_power;
                                    if (sensor_power == 1'b0)
                                        power_off_pulse <= 1'b1;
                                    else
                                        power_on_pulse <= 1'b1;
                                    phase_cnt <= 4'd0;
                                end else begin
                                    phase_cnt <= phase_cnt + 4'd1;
                                end
                            end

                            3'd4: begin  // FULL_CYCLE: OFF@32, ON@64, OFF@96
                                case (sample_cnt)
                                    7'd31: begin
                                        sensor_power <= 1'b1;
                                        power_off_pulse <= 1'b1;
                                    end
                                    7'd63: begin
                                        sensor_power <= 1'b0;
                                        power_on_pulse <= 1'b1;
                                    end
                                    7'd95: begin
                                        sensor_power <= 1'b1;
                                        power_off_pulse <= 1'b1;
                                    end
                                endcase
                            end

                            default: begin
                                // unknown mode — no power change
                            end
                        endcase

                        if (sample_cnt == 7'd127) begin
                            sample_cnt <= 7'd0;
                            state <= ST_DONE;
                        end else begin
                            sample_cnt <= sample_cnt + 7'd1;
                        end
                    end
                end

                ST_DONE: begin
                    sensor_power <= 1'b1;
                    state <= ST_IDLE;
                end

                default: begin
                    state <= ST_IDLE;
                    sensor_power <= 1'b1;
                end
            endcase
        end
    end

endmodule
