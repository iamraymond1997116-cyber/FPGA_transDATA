// SIM_DEPS: ad7606_if.v
// ============================================================================
// Testbench: tb_ad7606_soft_reset
// Verifies the soft_rst_n port added to ad7606_if for baseline-doubling fix.
//
// Checks:
//   1) After global rst_n release, ad_reset stays high for RESET_CYCLES, then low.
//   2) Pulling soft_rst_n low at runtime forces ad_reset high again.
//   3) Releasing soft_rst_n keeps ad_reset high for the full RESET_CYCLES count.
//   4) soft_rst_n=1 with normal rst_cnt rolloff: ad_reset goes low again.
// ============================================================================
`timescale 1ns / 1ps

module tb_ad7606_soft_reset;
    // Shrink RESET_CYCLES to keep sim fast (default is 16'hffff, ~65k cycles)
    localparam integer RESET_CYCLES_TB = 32;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic soft_rst_n = 1'b1;
    logic [15:0] ad_data = 16'h0000;
    logic ad_busy = 1'b0;
    logic first_data = 1'b0;

    wire [2:0]  ad_os;
    wire        ad_cs;
    wire        ad_rd;
    wire        ad_reset;
    wire        ad_convstab;
    wire        ad_data_valid;
    wire [15:0] ad_ch1, ad_ch2, ad_ch3, ad_ch4, ad_ch5, ad_ch6, ad_ch7, ad_ch8;

    integer err_count = 0;
    integer high_cnt;
    integer low_cnt;

    ad7606_if #(
        .RESET_CYCLES(RESET_CYCLES_TB)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .soft_rst_n(soft_rst_n),
        .ad_data(ad_data),
        .ad_busy(ad_busy),
        .first_data(first_data),
        .ad_os(ad_os),
        .ad_cs(ad_cs),
        .ad_rd(ad_rd),
        .ad_reset(ad_reset),
        .ad_convstab(ad_convstab),
        .ad_data_valid(ad_data_valid),
        .ad_ch1(ad_ch1), .ad_ch2(ad_ch2), .ad_ch3(ad_ch3), .ad_ch4(ad_ch4),
        .ad_ch5(ad_ch5), .ad_ch6(ad_ch6), .ad_ch7(ad_ch7), .ad_ch8(ad_ch8)
    );

    always #5 clk = ~clk;

    task automatic check(input logic cond, input string msg);
        if (!cond) begin
            $display("  [FAIL] %s", msg);
            err_count = err_count + 1;
        end
    endtask

    // Count ad_reset high cycles during a window
    task automatic count_reset(input integer cycles, output integer hi, output integer lo);
        hi = 0; lo = 0;
        repeat (cycles) begin
            @(posedge clk);
            if (ad_reset) hi = hi + 1; else lo = lo + 1;
        end
    endtask

    initial begin
        // ── Phase 1: power-on reset ──
        rst_n = 1'b0;
        soft_rst_n = 1'b1;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;

        // Right after rst_n release: should be HIGH for ~RESET_CYCLES
        count_reset(RESET_CYCLES_TB, high_cnt, low_cnt);
        check(high_cnt >= RESET_CYCLES_TB - 2,
              $sformatf("Phase1 expected ad_reset high during init reset window, got hi=%0d", high_cnt));

        // After init window: should settle LOW
        repeat (8) @(posedge clk);
        check(ad_reset === 1'b0, "Phase1 ad_reset should be LOW after init window");

        // ── Phase 2: soft reset pulse triggers ad_reset HIGH ──
        @(posedge clk); soft_rst_n = 1'b0;
        @(posedge clk);
        @(posedge clk);
        check(ad_reset === 1'b1, "Phase2 soft_rst_n low -> ad_reset must go HIGH");

        // Hold soft_rst_n low; ad_reset stays HIGH
        repeat (10) @(posedge clk);
        check(ad_reset === 1'b1, "Phase2 ad_reset must stay HIGH while soft_rst_n low");

        // ── Phase 3: release soft_rst_n; ad_reset stays HIGH for RESET_CYCLES then drops ──
        @(posedge clk); soft_rst_n = 1'b1;
        count_reset(RESET_CYCLES_TB, high_cnt, low_cnt);
        check(high_cnt >= RESET_CYCLES_TB - 2,
              $sformatf("Phase3 soft reset window expected high_cnt~%0d, got %0d", RESET_CYCLES_TB, high_cnt));

        repeat (8) @(posedge clk);
        check(ad_reset === 1'b0, "Phase3 ad_reset should return LOW after soft reset window");

        // ── Phase 4: global rst_n takes priority over soft_rst_n ──
        @(posedge clk); rst_n = 1'b0; soft_rst_n = 1'b1;
        @(posedge clk);
        check(ad_reset === 1'b0, "Phase4 global rst_n LOW should force ad_reset LOW");

        if (err_count == 0) begin
            $display("[PASS] tb_ad7606_soft_reset: all 4 phases verified");
        end else begin
            $display("[FAIL] tb_ad7606_soft_reset: %0d assertions failed", err_count);
            $fatal(1, "tb_ad7606_soft_reset failed");
        end
        $finish;
    end

    // Watchdog
    initial begin
        #200000;
        $display("[FAIL] tb_ad7606_soft_reset: watchdog timeout");
        $fatal(1, "timeout");
    end
endmodule
