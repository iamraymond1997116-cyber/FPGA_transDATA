`timescale 1ns / 1ps

module tb_trigger_chain;
    // ============================================================
    // Clock and reset
    // ============================================================
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    // ============================================================
    // ADC simulation
    // ============================================================
    reg adc_valid = 1'b0;
    reg signed [15:0] adc_ch1 = 16'sd0;
    reg signed [15:0] adc_ch2 = 16'sd0;

    // ============================================================
    // Power control signals
    // ============================================================
    wire sensor_power;
    wire power_on_pulse;
    wire capture_trigger;
    /* verilator lint_off UNUSEDSIGNAL */
    wire power_off_pulse;
    /* verilator lint_on UNUSEDSIGNAL */

    // ============================================================
    // Capture signals
    // ============================================================
    wire capture_done;
    wire [6:0] capture_buffer_addr;
    wire signed [15:0] capture_buffer_ch1_data;
    wire signed [15:0] capture_buffer_ch2_data;
    wire capture_buffer_we;

    // ============================================================
    // BRAM (inferred, 128x16 per channel) -- mirrors top-level
    // ============================================================
    reg signed [15:0] capture_bram_ch1 [0:127];
    reg signed [15:0] capture_bram_ch2 [0:127];

    // ============================================================
    // UART streamer signals
    // ============================================================
    /* verilator lint_off UNUSEDSIGNAL */
    wire uart_txd;
    /* verilator lint_on UNUSEDSIGNAL */
    wire uart_busy;
    wire [6:0] uart_raw_addr;
    wire signed [15:0] uart_read_ch1 = capture_bram_ch1[uart_raw_addr];
    wire signed [15:0] uart_read_ch2 = capture_bram_ch2[uart_raw_addr];

    // ============================================================
    // Top-level FSM registers (mirrors transient_puf_v60_top.v:194-226)
    // ============================================================
    reg [2:0] mode_select = 3'd0;
    reg [2:0] capture_mode = 3'd0;
    reg capture_start   = 1'b0;
    reg capture_req     = 1'b1;
    reg capture_done_d  = 1'b0;
    reg [7:0] uart_txn_counter = 8'd0;
    reg [15:0] sample_id = 16'd0;
    reg        sample_id_pending = 1'b0;
    wire [2:0] mode_idx = capture_mode;
    reg uart_send       = 1'b0;
    reg uart_busy_seen  = 1'b1;  // first trigger skips UART-busy gate

    // ============================================================
    // Test state machine
    // ============================================================
    localparam ST_INIT         = 0;
    localparam ST_RESET        = 1;
    localparam ST_WAIT_START   = 2;
    localparam ST_PROPAGATE1   = 3;
    localparam ST_FEED_ADC     = 4;
    localparam ST_WAIT_DONE    = 5;
    localparam ST_WAIT_UART_HI = 6;
    localparam ST_WAIT_UART_LO = 7;
    localparam ST_VERIFY       = 8;
    localparam ST_DONE         = 9;
    reg [3:0] test_state = ST_INIT;

    // Verification counters and temporary registers
    integer cycle_num;
    integer adc_feed_cnt;
    integer wait_cnt;
    integer capture_done_seen;
    integer capture_start_seen;
    integer txn_expected;
    integer txn_errors;
    integer mode_prev;
    integer mode_toggles_ok;
    reg capture_start_prev;
    integer premature_fires;
    integer total_cycles;
    integer max_cycles;
    reg test_done;

    // ============================================================
    // DUT: sensor_power_control
    // ============================================================
    sensor_power_control dut_power (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(capture_start),
        .mode(capture_mode),
        .sample_tick(capture_buffer_we),
        .sensor_power(sensor_power),
        .power_on_pulse(power_on_pulse),
        .capture_trigger(capture_trigger),
        .power_off_pulse(power_off_pulse)
    );

    // ============================================================
    // DUT: transient_capture
    // ============================================================
    transient_capture #(.CAPTURE_COUNT(128)) dut_cap (
        .clk(clk),
        .rst_n(rst_n),
        .adc_valid(adc_valid),
        .adc_ch1(adc_ch1),
        .adc_ch2(adc_ch2),
        .trigger(capture_trigger),
        .capture_done(capture_done),
        .buffer_addr(capture_buffer_addr),
        .buffer_ch1_data(capture_buffer_ch1_data),
        .buffer_ch2_data(capture_buffer_ch2_data),
        .buffer_we(capture_buffer_we)
    );

    // ============================================================
    // DUT: capture_uart_streamer (internally instantiates uart_tx)
    // ============================================================
    capture_uart_streamer #(.CLKS_PER_BIT(10)) dut_uart_streamer (
        .clk(clk),
        .rst_n(rst_n),
        .send(uart_send),
        .mode(capture_mode),
        .sample_id(sample_id),
        .mode_idx(mode_idx),
        .txn_id(uart_txn_counter),
        .sensor_power(sensor_power),
        .raw_ch1_data(uart_read_ch1),
        .raw_ch2_data(uart_read_ch2),
        .raw_addr(uart_raw_addr),
        .txd(uart_txd),
        .busy(uart_busy)
    );

    // ============================================================
    // BRAM write port
    // ============================================================
    always @(posedge clk) begin
        if (capture_buffer_we) begin
            capture_bram_ch1[capture_buffer_addr] <= capture_buffer_ch1_data;
            capture_bram_ch2[capture_buffer_addr] <= capture_buffer_ch2_data;
        end
    end

    // ============================================================
    // Top-level FSM (exact replica of transient_puf_v60_top.v:194-226)
    // ============================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mode_select <= 3'd0;
            capture_mode <= 3'd0;
            uart_txn_counter <= 8'd0;
            sample_id <= 16'd0;
            capture_req     <= 1'b1;
            capture_done_d  <= 1'b0;
            uart_busy_seen  <= 1'b1;
        end else begin
            uart_send    <= 1'b0;
            capture_start <= 1'b0;

            capture_done_d <= capture_done;

            if (capture_done && !capture_done_d) begin
                uart_send <= 1'b1;
                uart_txn_counter <= uart_txn_counter + 8'd1;
                capture_req <= 1'b1;
                if (capture_mode == 3'd4)
                    sample_id_pending <= 1'b1;
                mode_select <= (mode_select == 3'd4) ? 3'd0 : mode_select + 3'd1;
                uart_busy_seen <= 1'b0;
            end

            if (uart_busy)
                uart_busy_seen <= 1'b1;

            if (!uart_busy && capture_req && !capture_start && uart_busy_seen) begin
                if (sample_id_pending) begin
                    sample_id <= sample_id + 16'd1;
                    sample_id_pending <= 1'b0;
                end
                capture_mode <= mode_select;
                capture_start <= 1'b1;
                capture_req <= 1'b0;
            end
        end
    end

    // ============================================================
    // Test state machine (single @(posedge clk) per procedure --
    //    required by Verilator --no-timing mode)
    // ============================================================
    always @(posedge clk) begin
        if (test_state == ST_INIT) begin
            $display("================================================================================");
            $display("tb_trigger_chain ENHANCED -- V6.0 full UART-chain simulation");
            $display("  Sensor power control + transient capture + capture UART streamer");
            $display("  Top-level FSM: DONE->UART.send->UART.busy^->UART.busyv->capture_start");
            $display("  Goal: catch premature capture_start race conditions");
            $display("================================================================================");

            // Initialize counters
            cycle_num          <= 0;
            capture_done_seen  <= 0;
            capture_start_seen <= 0;
            txn_expected       <= 0;
            txn_errors         <= 0;
            mode_prev          <= 1'b0;
            mode_toggles_ok    <= 1;
            capture_start_prev <= 1'b0;
            premature_fires    <= 0;
            total_cycles       <= 0;
            max_cycles         <= 3000000;
            adc_ch1            <= 16'sd0;
            adc_ch2            <= 16'sd0;
            test_done          <= 0;

            rst_n <= 1'b0;
            test_state <= ST_RESET;
            wait_cnt <= 5;
        end

        // ---- Counters active in all states ----
        total_cycles <= total_cycles + 1;
        if (total_cycles > max_cycles && !test_done) begin
            $display("FAIL: Timeout at %0d cycles", total_cycles);
            $finish;
        end

        capture_start_prev <= capture_start;
        if (capture_start && !capture_start_prev) begin
            capture_start_seen <= capture_start_seen + 1;
        end
        if (capture_done && !capture_done_d) begin
            capture_done_seen <= capture_done_seen + 1;
            if (uart_txn_counter != txn_expected) begin
                $display("ERROR: TXN mismatch at cycle %0d: got %0d, expected %0d",
                         total_cycles, uart_txn_counter, txn_expected + 1);
                txn_errors <= txn_errors + 1;
            end
            txn_expected <= txn_expected + 1;

            if (capture_done_seen > 0 && mode_select == mode_prev) begin
                $display("ERROR: MODE did not toggle at cycle %0d", total_cycles);
                mode_toggles_ok <= 0;
            end
            mode_prev <= mode_select;
        end
        if (capture_start && !capture_start_prev && !uart_busy_seen && !uart_busy) begin
            $display("RACE DETECTED at cycle %0d: capture_start while uart_busy_seen=%0d",
                     total_cycles, uart_busy_seen);
            premature_fires <= premature_fires + 1;
        end

        // ---- Test state machine ----
        case (test_state)

            ST_RESET: begin
                if (wait_cnt > 0) begin
                    wait_cnt <= wait_cnt - 1;
                end else begin
                    rst_n <= 1'b1;
                    $display("Reset released");
                    $display("------------------------------------------------------------------------");
                    $display("=== Cycle %0d: waiting for capture_start ===", cycle_num);
                    test_state <= ST_WAIT_START;
                end
            end

            ST_WAIT_START: begin
                if (capture_start) begin
                    $display("capture_start fired (capture_start_seen=%0d)", capture_start_seen);
                    $display("Waiting for capture_trigger (power controller ready)...");
                    test_state <= ST_PROPAGATE1;
                end
            end

            ST_PROPAGATE1: begin
                if (capture_trigger) begin
                    $display("capture_trigger fired, feeding 128 ADC samples (mode=%0d)...", capture_mode);
                    adc_valid <= 1'b1;
                    adc_feed_cnt <= 0;
                    test_state <= ST_FEED_ADC;
                end
            end

            ST_FEED_ADC: begin
                if (adc_feed_cnt < 128) begin
                    adc_ch1 <= adc_ch1 + 16'sd1;
                    adc_ch2 <= adc_ch2 + 16'sd2;
                    adc_feed_cnt <= adc_feed_cnt + 1;
                end else begin
                    adc_valid <= 1'b0;
                    $display("ADC feeding complete, waiting for capture_done...");
                    test_state <= ST_WAIT_DONE;
                end
            end

            ST_WAIT_DONE: begin
                if (capture_done) begin
                    $display("capture_done fired (capture_done_seen=%0d)", capture_done_seen);
                    $display("       TXN=%0d  MODE=%0d  uart_busy_seen=%0d",
                             uart_txn_counter, mode_select, uart_busy_seen);
                    $display("Waiting for UART to transmit (uart_busy high then low)...");
                    test_state <= ST_WAIT_UART_HI;
                end
            end

            ST_WAIT_UART_HI: begin
                if (uart_busy) begin
                    $display("uart_busy went HIGH at cycle %0d", total_cycles);
                    test_state <= ST_WAIT_UART_LO;
                end
            end

            ST_WAIT_UART_LO: begin
                if (!uart_busy) begin
                    $display("uart_busy went LOW at cycle %0d (UART done)", total_cycles);
                    cycle_num <= cycle_num + 1;
                    if (cycle_num < 5) begin  // six captures cover one full 5-mode sample plus next FULL
                        $display("------------------------------------------------------------------------");
                        $display("=== Cycle %0d: waiting for capture_start ===", cycle_num + 1);
                        test_state <= ST_WAIT_START;
                    end else begin
                        $display("------------------------------------------------------------------------");
                        test_state <= ST_VERIFY;
                    end
                end
            end

            ST_VERIFY: begin
                $display("================================================================================");
                $display("VERIFICATION RESULTS");
                $display("================================================================================");

                if (capture_done_seen !== 6) begin
                    $display("FAIL: capture_done_seen=%0d (expected 6)", capture_done_seen);
                    $finish;
                end
                $display("PASS: capture_done_seen=%0d (expected 6)", capture_done_seen);

                if (capture_start_seen !== 6) begin
                    $display("FAIL: capture_start_seen=%0d (expected 6)", capture_start_seen);
                    $finish;
                end
                $display("PASS: capture_start_seen=%0d (expected 6)", capture_start_seen);

                if (txn_errors !== 0) begin
                    $display("FAIL: TXN errors=%0d", txn_errors);
                    $finish;
                end
                if (uart_txn_counter !== 6) begin
                    $display("FAIL: uart_txn_counter=%0d (expected 6)", uart_txn_counter);
                    $finish;
                end
                $display("PASS: uart_txn_counter=%0d (expected 6), TXN errors=%0d",
                         uart_txn_counter, txn_errors);

                if (mode_toggles_ok !== 1) begin
                    $display("FAIL: MODE did not toggle correctly");
                    $finish;
                end
                if (mode_select !== 3'd1) begin
                    $display("FAIL: mode_select=%0d (expected 1 after 6 captures)", mode_select);
                    $finish;
                end
                $display("PASS: mode_select=%0d (expected 1 after 6 captures)", mode_select);

                if (sample_id !== 16'd1) begin
                    $display("FAIL: sample_id=%0d (expected 1 after one complete FCYC)", sample_id);
                    $finish;
                end
                $display("PASS: sample_id=%0d (increments once per 5-mode sample)", sample_id);

                if (premature_fires !== 0) begin
                    $display("FAIL: premature_fires=%0d", premature_fires);
                    $finish;
                end
                $display("PASS: premature_fires=%0d (no race conditions detected)", premature_fires);

                if (uart_busy_seen !== 1'b1) begin
                    $display("FAIL: uart_busy_seen=%0d (expected 1)", uart_busy_seen);
                    $finish;
                end
                $display("PASS: uart_busy_seen=%0d (busy gating intact)", uart_busy_seen);

                $display("================================================================================");
                $display("ALL CHECKS PASSED");
                $display("  capture_done_seen=%0d  capture_start_seen=%0d  TXN=%0d  MODE=%0d",
                         capture_done_seen, capture_start_seen, uart_txn_counter, mode_select);
                $display("  premature_fires=%0d  tx_errors=%0d  total_cycles=%0d",
                         premature_fires, txn_errors, total_cycles);
                $display("================================================================================");
                $display("PASS");
                test_state <= ST_DONE;
            end

            ST_DONE: begin
                test_done <= 1;
                $finish;
            end

        endcase
    end

endmodule
