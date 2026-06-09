`timescale 1ns / 1ps

module tb_trigger_chain;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg trigger = 1'b0;
    reg [2:0] mode = 3'd0;
    reg adc_valid = 1'b0;
    reg signed [15:0] adc_ch1 = 16'sd0;
    reg signed [15:0] adc_ch2 = 16'sd0;
    wire sensor_power;
    wire power_on_pulse;
    wire power_off_pulse;
    wire capture_done;
    wire [6:0] buffer_addr;
    wire signed [15:0] buffer_ch1_data;
    wire signed [15:0] buffer_ch2_data;
    wire buffer_we;
    integer i;

    sensor_power_control dut_power (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(trigger),
        .mode(mode),
        .sample_tick(buffer_we),
        .sensor_power(sensor_power),
        .power_on_pulse(power_on_pulse),
        .power_off_pulse(power_off_pulse)
    );

    transient_capture #(.CAPTURE_COUNT(128)) dut_cap (
        .clk(clk),
        .rst_n(rst_n),
        .adc_valid(adc_valid),
        .adc_ch1(adc_ch1),
        .adc_ch2(adc_ch2),
        .trigger(power_on_pulse),
        .capture_done(capture_done),
        .buffer_addr(buffer_addr),
        .buffer_ch1_data(buffer_ch1_data),
        .buffer_ch2_data(buffer_ch2_data),
        .buffer_we(buffer_we)
    );

    always #5 clk = ~clk;

    initial begin
        $display("tb_trigger_chain start");
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);
        trigger = 1'b1;
        @(posedge clk);
        trigger = 1'b0;

        for (i = 0; i < 256; i = i + 1) begin
            @(posedge clk);
            adc_valid = 1'b1;
            adc_ch1 = adc_ch1 + 16'sd1;
            adc_ch2 = adc_ch2 + 16'sd2;
        end
        adc_valid = 1'b0;

        repeat (20) @(posedge clk);
        $display("capture_done=%0d power_on_pulse=%0d power_off_pulse=%0d", capture_done, power_on_pulse, power_off_pulse);
        $finish;
    end

endmodule
