// ============================================================================
// transient_puf_v60_top — V6.x Multi-Mode Transient Capture Top-Level
//
// 5 capture modes, auto-cycling:
//   FULL → PCUT → NCUT → EXTR → FCYC → FULL → ...
//
// Sensor power:    1=OFF, 0=ON (PMOS control)
// Capture trigger:  fires at start of sampling window (128 ADC samples)
// UART:            ASCII frames, 1 Mbps, header with mode name
// ============================================================================
`timescale 1ns / 1ps

module transient_puf_v60_top (
    input  wire        sys_clk_p,
    input  wire        sys_clk_n,
    input  wire        key1_n,
    input  wire        key2_n,
    input  wire        uart_rxd,
    input  wire [15:0] ad7606_data,
    input  wire        ad7606_busy,
    input  wire        ad7606_first_data,
    output wire        uart_txd,
    output wire        led1,
    output wire        led2,
    output wire        led3,
    output wire        led4,
    output wire [2:0]  ad7606_os,
    output wire        ad7606_cs,
    output wire        ad7606_rd,
    output wire        ad7606_reset,
    output wire        ad7606_convstab,
    output wire        lcd_dclk,
    output wire        lcd_hs,
    output wire        lcd_vs,
    output wire        lcd_de,
    output wire [7:0]  lcd_r,
    output wire [7:0]  lcd_g,
    output wire [7:0]  lcd_b
);

    localparam [7:0] VERSION_MAJOR = 8'd6;
    localparam [7:0] VERSION_MINOR = 8'd3;

    // ── Mode encoding (3-bit) ──
    localparam [2:0] MODE_FULL        = 3'd0;
    localparam [2:0] MODE_POS_CUT     = 3'd1;
    localparam [2:0] MODE_NEG_CUT     = 3'd2;
    localparam [2:0] MODE_EXTREMA_CYC = 3'd3;
    localparam [2:0] MODE_FULL_CYCLE  = 3'd4;
    localparam [2:0] MODE_MAX         = 3'd4;

    // ── Internal wires / regs ──
    wire clk_200m;
    wire pixel_clk;
    wire system_reset_n;
    reg  system_reset_n_reg = 1'b0;
    reg  [15:0] startup_reset_counter = 16'd0;

    wire key1_stable_pressed;
    wire key1_press_pulse;
    wire key2_stable_pressed;
    wire key2_press_pulse;

    wire ad_data_valid;
    wire signed [15:0] ad_ch1;
    wire signed [15:0] ad_ch2;
    wire signed [15:0] ad_ch3_unused;
    wire signed [15:0] ad_ch4_unused;
    wire signed [15:0] ad_ch5_unused;
    wire signed [15:0] ad_ch6_unused;
    wire signed [15:0] ad_ch7_unused;
    wire signed [15:0] ad_ch8_unused;

    reg  [2:0] mode_select    = MODE_FULL;
    reg  [2:0] capture_mode   = MODE_FULL;
    reg        capture_start  = 1'b0;
    reg        capture_req    = 1'b1;
    reg        capture_done_d = 1'b0;
    wire       sensor_power;
    wire       power_on_pulse;
    wire       power_off_pulse;
    wire       capture_trigger;     // unified trigger for transient_capture
    wire       early_precharge;     // pre-assert ON during UART busy (NEG_CUT)

    wire capture_done;
    wire [6:0] capture_buffer_addr;
    wire signed [15:0] capture_buffer_ch1_data;
    wire signed [15:0] capture_buffer_ch2_data;
    wire capture_buffer_we;

    reg [7:0] uart_txn_counter = 8'd0;
    reg uart_send = 1'b0;
    reg uart_busy_seen = 1'b0;
    wire uart_busy;
    wire [6:0] uart_raw_addr;

    // ── Clocking ──
    IBUFDS #(
        .DIFF_TERM("FALSE"),
        .IBUF_LOW_PWR("TRUE")
    ) sys_clk_buf (
        .I(sys_clk_p),
        .IB(sys_clk_n),
        .O(clk_200m)
    );

    pixel_clock_divider #(
        .HALF_DIVIDE(11)
    ) pixel_clock_divider_inst (
        .clk_in(clk_200m),
        .clk_out(pixel_clk)
    );

    // ── Reset sequencer ──
    button_debounce #(.DEBOUNCE_CYCLES(200000)) key1_debounce_inst (
        .clk(pixel_clk),
        .noisy(~key1_n),
        .stable(key1_stable_pressed),
        .press_pulse(key1_press_pulse)
    );

    button_debounce #(.DEBOUNCE_CYCLES(200000)) key2_debounce_inst (
        .clk(pixel_clk),
        .noisy(~key2_n),
        .stable(key2_stable_pressed),
        .press_pulse(key2_press_pulse)
    );

    always @(posedge pixel_clk or negedge system_reset_n_reg) begin
        if (!system_reset_n_reg) begin
            if (startup_reset_counter == 16'd1023) begin
                system_reset_n_reg <= 1'b1;
            end else begin
                startup_reset_counter <= startup_reset_counter + 16'd1;
            end
        end
    end

    assign system_reset_n = system_reset_n_reg;

    // ── ADC interface ──
    ad7606_if ad7606_if_inst (
        .clk(pixel_clk),
        .rst_n(system_reset_n),
        .ad_data(ad7606_data),
        .ad_busy(ad7606_busy),
        .first_data(ad7606_first_data),
        .ad_os(ad7606_os),
        .ad_cs(ad7606_cs),
        .ad_rd(ad7606_rd),
        .ad_reset(ad7606_reset),
        .ad_convstab(ad7606_convstab),
        .ad_data_valid(ad_data_valid),
        .ad_ch1(ad_ch1),
        .ad_ch2(ad_ch2),
        .ad_ch3(ad_ch3_unused),
        .ad_ch4(ad_ch4_unused),
        .ad_ch5(ad_ch5_unused),
        .ad_ch6(ad_ch6_unused),
        .ad_ch7(ad_ch7_unused),
        .ad_ch8(ad_ch8_unused)
    );

    assign early_precharge = uart_busy && (mode_select == MODE_NEG_CUT);

    // ── Power control (5-mode) ──
    sensor_power_control sensor_power_control_inst (
        .clk(pixel_clk),
        .rst_n(system_reset_n),
        .trigger(capture_start),
        .mode(capture_mode),
        .sample_tick(capture_buffer_we),
        .early_precharge(early_precharge),
        .sensor_power(sensor_power),
        .power_on_pulse(power_on_pulse),
        .power_off_pulse(power_off_pulse),
        .capture_trigger(capture_trigger)
    );

    // ── Transient capture (triggered by unified capture_trigger) ──
    transient_capture #(.CAPTURE_COUNT(128)) transient_capture_inst (
        .clk(pixel_clk),
        .rst_n(system_reset_n),
        .adc_valid(ad_data_valid),
        .adc_ch1(ad_ch1),
        .adc_ch2(ad_ch2),
        .trigger(capture_trigger),
        .capture_done(capture_done),
        .buffer_addr(capture_buffer_addr),
        .buffer_ch1_data(capture_buffer_ch1_data),
        .buffer_ch2_data(capture_buffer_ch2_data),
        .buffer_we(capture_buffer_we)
    );

    // ── Dual BRAM (128 × 16-bit each channel) ──
    reg signed [15:0] capture_bram_ch1 [0:127];
    reg signed [15:0] capture_bram_ch2 [0:127];
    wire signed [15:0] uart_read_ch1 = capture_bram_ch1[uart_raw_addr];
    wire signed [15:0] uart_read_ch2 = capture_bram_ch2[uart_raw_addr];

    always @(posedge pixel_clk) begin
        if (capture_buffer_we) begin
            capture_bram_ch1[capture_buffer_addr] <= capture_buffer_ch1_data;
            capture_bram_ch2[capture_buffer_addr] <= capture_buffer_ch2_data;
        end
    end

    // ── UART streamer ──
    capture_uart_streamer #(.CLKS_PER_BIT(10), .VERSION_MAJOR(VERSION_MAJOR), .VERSION_MINOR(VERSION_MINOR)) capture_uart_streamer_inst (
        .clk(pixel_clk),
        .rst_n(system_reset_n),
        .send(uart_send),
        .mode(capture_mode),
        .txn_id(uart_txn_counter),
        .sensor_power(sensor_power),
        .raw_ch1_data(uart_read_ch1),
        .raw_ch2_data(uart_read_ch2),
        .raw_addr(uart_raw_addr),
        .txd(uart_txd),
        .busy(uart_busy)
    );

    // ── Top-level control FSM ──
    always @(posedge pixel_clk) begin
        uart_send <= 1'b0;
        capture_start <= 1'b0;

        if (!system_reset_n) begin
            mode_select    <= MODE_FULL;
            capture_mode   <= MODE_FULL;
            uart_txn_counter <= 8'd0;
            capture_req    <= 1'b1;
            capture_done_d <= 1'b0;
            uart_busy_seen <= 1'b1;    // first trigger skips busy check
        end else begin
            capture_done_d <= capture_done;

            // Capture done → send UART frame
            if (capture_done && !capture_done_d) begin
                uart_send <= 1'b1;
                uart_txn_counter <= uart_txn_counter + 8'd1;
                capture_req <= 1'b1;
                // Cycle through 5 modes: 0→1→2→3→4→0→...
                mode_select <= (mode_select == MODE_MAX) ? MODE_FULL : mode_select + 3'd1;
                uart_busy_seen <= 1'b0;
            end

            // Track that UART became busy
            if (uart_busy)
                uart_busy_seen <= 1'b1;

            // Start next capture after UART finishes
            if (!uart_busy && capture_req && !capture_start && uart_busy_seen) begin
                capture_mode <= mode_select;
                capture_start <= 1'b1;
                capture_req <= 1'b0;
            end
        end
    end

    // ── LCD display ──
    lcd_version_mode_display #(.VERSION_MAJOR(VERSION_MAJOR), .VERSION_MINOR(VERSION_MINOR)) lcd_version_mode_display_inst (
        .pixel_clk(pixel_clk),
        .rst_n(system_reset_n),
        .mode(mode_select),
        .lcd_hs(lcd_hs),
        .lcd_vs(lcd_vs),
        .lcd_de(lcd_de),
        .lcd_r(lcd_r),
        .lcd_g(lcd_g),
        .lcd_b(lcd_b)
    );

    assign lcd_dclk = ~pixel_clk;

    // ── LED indicators ──
    assign led1 = 1'b1;                          // Power ON
    assign led2 = ~uart_busy;                     // UART idle
    assign led3 = ~mode_select[0];                // mode bit 0
    assign led4 = sensor_power;                   // sensor power state

endmodule
