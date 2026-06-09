// SIM_DEPS: sensor_power_control.v
// ============================================================================
// Testbench: tb_sensor_power_control_v60
// Verifies 5-mode power sequencing: FULL, POS_CUT, NEG_CUT, EXTREMA_CYCLE, FULL_CYCLE
//
// CHECK TIMING: sensor_power is checked BEFORE each sample_tick (simulates ADC
// sampling instant). The DUT uses NB assignments that take effect one cycle
// after the transition sample is processed.
// ============================================================================
`timescale 1ns / 1ps

module tb_sensor_power_control_v60;
    logic clk = 1'b0;
    logic rst_n = 1'b1;
    logic trigger = 1'b0;
    logic [2:0] mode = 3'd0;
    logic sample_tick = 1'b0;
    wire  sensor_power;
    wire  power_on_pulse;
    wire  power_off_pulse;
    wire  capture_trigger;

    integer sample_cnt;
    integer err_count = 0;
    logic expected_pwr;
    logic expected_pwr2;
    integer i;

    sensor_power_control dut (
        .clk(clk), .rst_n(rst_n), .trigger(trigger), .mode(mode),
        .sample_tick(sample_tick),
        .early_precharge(1'b0),  // TB: no early precharge (test standard path)
        .sensor_power(sensor_power),
        .power_on_pulse(power_on_pulse),
        .power_off_pulse(power_off_pulse),
        .capture_trigger(capture_trigger)
    );

    always #55 clk = ~clk;

    // ── helpers ──────────────────────────────────────────────
    task automatic reset_dut;
        rst_n = 1'b0;
        trigger = 1'b0;
        sample_tick = 1'b0;
        mode = 3'd0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);
    endtask

    task automatic pulse_trigger;
        trigger = 1'b1;
        @(posedge clk);
        trigger = 1'b0;
        @(posedge clk);
    endtask

    // ── Macro: run one 128-sample cycle with check-BEFORE-sample logic ──
    // Caller sets mode, calls pulse_trigger, waits settle, then calls this.
    // check_fn is evaluated BEFORE each sample_tick to match ADC timing.
    task automatic run_samples_check;
        begin
            sample_cnt = 0;
            repeat (128) begin
                @(posedge clk);
                // ── CHECK before sample_tick ──
                expected_pwr = 1'bx;
                case (mode)
                    3'd0: expected_pwr = (sample_cnt < 64) ? 1'b0 : 1'b1;
                    3'd1: expected_pwr = (sample_cnt < 8)  ? 1'b0 : 1'b1;
                    3'd2: expected_pwr = (sample_cnt < 8)  ? 1'b1 : 1'b0;
                    3'd3: begin  // 8-sample phases (128/8=16): ON 0-7, OFF 8-15, ...
                        if      (sample_cnt < 8)   expected_pwr = 1'b0;
                        else if (sample_cnt < 16)  expected_pwr = 1'b1;
                        else if (sample_cnt < 24)  expected_pwr = 1'b0;
                        else if (sample_cnt < 32)  expected_pwr = 1'b1;
                        else if (sample_cnt < 40)  expected_pwr = 1'b0;
                        else if (sample_cnt < 48)  expected_pwr = 1'b1;
                        else if (sample_cnt < 56)  expected_pwr = 1'b0;
                        else if (sample_cnt < 64)  expected_pwr = 1'b1;
                        else if (sample_cnt < 72)  expected_pwr = 1'b0;
                        else if (sample_cnt < 80)  expected_pwr = 1'b1;
                        else if (sample_cnt < 88)  expected_pwr = 1'b0;
                        else if (sample_cnt < 96)  expected_pwr = 1'b1;
                        else if (sample_cnt < 104) expected_pwr = 1'b0;
                        else if (sample_cnt < 112) expected_pwr = 1'b1;
                        else if (sample_cnt < 120) expected_pwr = 1'b0;
                        else                       expected_pwr = 1'b1;
                    end
                    3'd4: begin
                        if      (sample_cnt < 32) expected_pwr = 1'b0;
                        else if (sample_cnt < 64) expected_pwr = 1'b1;
                        else if (sample_cnt < 96) expected_pwr = 1'b0;
                        else                      expected_pwr = 1'b1;
                    end
                endcase

                if (sensor_power !== expected_pwr) begin
                    $error("[FAIL] mode=%0d sample %0d: expected %0d, got %0d",
                           mode, sample_cnt, expected_pwr, sensor_power);
                    err_count++;
                end

                sample_tick = 1'b1;
                @(posedge clk);
                sample_tick = 1'b0;
                sample_cnt++;
            end
        end
    endtask

    // ── main ─────────────────────────────────────────────────
    initial begin
        // ============================================
        // Test 1: MODE_FULL
        // ============================================
        $display("=== Test 1: MODE_FULL ===");
        reset_dut();
        mode = 3'd0;
        pulse_trigger();
        repeat (5) @(posedge clk);
        run_samples_check();

        // Verify return to IDLE
        repeat (5) @(posedge clk);
        if (sensor_power !== 1'b1) begin
            $error("[FAIL] FULL: sensor_power should return to OFF(1) in IDLE");
            err_count++;
        end

        // ============================================
        // Test 2: MODE_POS_CUT
        // ============================================
        $display("=== Test 2: MODE_POS_CUT ===");
        reset_dut();
        mode = 3'd1;
        pulse_trigger();
        repeat (5) @(posedge clk);
        run_samples_check();

        // ============================================
        // Test 3: MODE_NEG_CUT
        // ============================================
        $display("=== Test 3: MODE_NEG_CUT ===");
        reset_dut();
        mode = 3'd2;
        pulse_trigger();
        repeat (1010) @(posedge clk);  // wait for precharge
        run_samples_check();

        // ============================================
        // Test 4: MODE_EXTREMA_CYCLE
        // ============================================
        $display("=== Test 4: MODE_EXTREMA_CYCLE ===");
        reset_dut();
        mode = 3'd3;
        pulse_trigger();
        repeat (5) @(posedge clk);
        run_samples_check();

        // ============================================
        // Test 5: MODE_FULL_CYCLE
        // ============================================
        $display("=== Test 5: MODE_FULL_CYCLE ===");
        reset_dut();
        mode = 3'd4;
        pulse_trigger();
        repeat (5) @(posedge clk);
        run_samples_check();

        // ============================================
        // Report
        // ============================================
        if (err_count == 0) begin
            $display("tb_sensor_power_control_v60 PASSED (all 5 modes)");
        end else begin
            $fatal(1, "tb_sensor_power_control_v60 FAILED with %0d errors", err_count);
        end
        $finish;
    end
endmodule
