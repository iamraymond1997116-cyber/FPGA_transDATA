// SIM_SKIP: standalone streamer test (duplicate module name, not part of main build)
`timescale 1ns / 1ps
module transient_puf_v60_top_test (
    input  wire        sys_clk_p, sys_clk_n,
    input  wire        key1_n, key2_n, uart_rxd,
    input  wire [15:0] ad7606_data,
    input  wire        ad7606_busy, ad7606_first_data,
    output wire        uart_txd,
    output wire        led1, led2, led3, led4,
    output wire [2:0]  ad7606_os,
    output wire        ad7606_cs, ad7606_rd, ad7606_reset, ad7606_convstab,
    output wire        lcd_dclk, lcd_hs, lcd_vs, lcd_de,
    output wire [7:0]  lcd_r, lcd_g, lcd_b
);
    wire clk_200m, pixel_clk;
    IBUFDS #(.DIFF_TERM("FALSE"),.IBUF_LOW_PWR("TRUE")) ib (.I(sys_clk_p),.IB(sys_clk_n),.O(clk_200m));
    pixel_clock_divider #(.HALF_DIVIDE(11)) pix (.clk_in(clk_200m),.clk_out(pixel_clk));

    reg [23:0] cnt = 24'd0;
    reg        uart_send = 1'b0;
    reg [7:0]  uart_txn = 8'hA5;
    reg        uart_spwr = 1'b0;
    wire       uart_busy;
    wire signed [15:0] ch1_data = 16'h1234;
    wire signed [15:0] ch2_data = 16'h5678;
    wire [6:0] uart_raw_addr;
    wire uart_txd_wire;

    capture_uart_streamer #(.CLKS_PER_BIT(10)) streamer (
        .clk(pixel_clk), .rst_n(1'b1),
        .send(uart_send), .mode(3'd0),
        .sample_id(16'd0), .mode_idx(3'd0),
        .txn_id(uart_txn), .sensor_power(uart_spwr),
        .raw_ch1_data(ch1_data), .raw_ch2_data(ch2_data),
        .raw_addr(uart_raw_addr),
        .txd(uart_txd_wire), .busy(uart_busy)
    );
    assign uart_txd = uart_txd_wire;

    always @(posedge pixel_clk) begin
        cnt <= cnt + 24'd1;
        uart_send <= 1'b0;
        // Trigger one frame every ~1.8 seconds
        if (cnt == 24'd0 && !uart_busy) begin
            uart_send <= 1'b1;
            uart_txn <= uart_txn + 8'd1;
            uart_spwr <= ~uart_spwr;
        end
    end

    assign led1 = ~uart_busy; assign led2 = 1'b1; assign led3 = 1'b1; assign led4 = 1'b1;
    assign lcd_dclk = 1'b0; assign lcd_hs = 1'b0; assign lcd_vs = 1'b0; assign lcd_de = 1'b0;
    assign lcd_r = 0; assign lcd_g = 0; assign lcd_b = 0;
    assign ad7606_os = 0; assign ad7606_cs = 1'b1; assign ad7606_rd = 1'b1;
    assign ad7606_reset = 1'b0; assign ad7606_convstab = 1'b0;
endmodule
