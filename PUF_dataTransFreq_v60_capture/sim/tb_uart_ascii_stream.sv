`timescale 1ns / 1ps

module tb_uart_ascii_stream;
    localparam integer CLKS_PER_BIT = 4;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg send = 1'b0;
    reg [2:0] mode = 3'd0;
    reg [15:0] sample_id = 16'd12;
    reg [2:0] mode_idx = 3'd0;
    reg [7:0] txn_id = 8'h3C;
    reg sensor_power = 1'b0;
    reg signed [15:0] raw_ch1_data = 16'sh1234;
    reg signed [15:0] raw_ch2_data = 16'sh5678;
    wire [6:0] raw_addr;
    wire txd;
    wire busy;

    capture_uart_streamer #(.CLKS_PER_BIT(CLKS_PER_BIT), .VERSION_MAJOR(8'd6), .VERSION_MINOR(8'd5)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .send(send),
        .mode(mode),
        .sample_id(sample_id),
        .mode_idx(mode_idx),
        .txn_id(txn_id),
        .sensor_power(sensor_power),
        .raw_ch1_data(raw_ch1_data),
        .raw_ch2_data(raw_ch2_data),
        .raw_addr(raw_addr),
        .txd(txd),
        .busy(busy)
    );

    always #5 clk = ~clk;

    task uart_recv_byte;
        output [7:0] byte_out;
        integer i;
        begin
            wait (txd == 1'b0);
            repeat (CLKS_PER_BIT + (CLKS_PER_BIT/2)) @(posedge clk);
            for (i = 0; i < 8; i = i + 1) begin
                byte_out[i] = txd;
                repeat (CLKS_PER_BIT) @(posedge clk);
            end
            if (txd !== 1'b1) begin
                $display("FAIL uart stop bit low");
                $finish;
            end
            repeat (CLKS_PER_BIT) @(posedge clk);
        end
    endtask

    task expect_byte;
        input [7:0] got;
        input [7:0] exp;
        input [8*64:1] msg;
        begin
            if (got !== exp) begin
                $display("FAIL %s got=%02x exp=%02x", msg, got, exp);
                $finish;
            end
        end
    endtask

    reg [7:0] b;
    integer i;

    initial begin
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);
        sensor_power = 1'b1;
        send = 1'b1;
        @(posedge clk);
        send = 1'b0;

        // Header: V6.5,SID=00012,MID=0,FULL,SPWR=1,TXN=3C\n
        uart_recv_byte(b); expect_byte(b, "V", "hdr V");
        uart_recv_byte(b); expect_byte(b, "6", "hdr 6");
        uart_recv_byte(b); expect_byte(b, ".", "hdr dot");
        uart_recv_byte(b); expect_byte(b, "5", "hdr minor");
        uart_recv_byte(b); expect_byte(b, ",", "hdr comma 0");
        uart_recv_byte(b); expect_byte(b, "S", "sid S");
        uart_recv_byte(b); expect_byte(b, "I", "sid I");
        uart_recv_byte(b); expect_byte(b, "D", "sid D");
        uart_recv_byte(b); expect_byte(b, "=", "sid eq");
        uart_recv_byte(b); expect_byte(b, "0", "sid d0");
        uart_recv_byte(b); expect_byte(b, "0", "sid d1");
        uart_recv_byte(b); expect_byte(b, "0", "sid d2");
        uart_recv_byte(b); expect_byte(b, "1", "sid d3");
        uart_recv_byte(b); expect_byte(b, "2", "sid d4");
        uart_recv_byte(b); expect_byte(b, ",", "sid comma");
        uart_recv_byte(b); expect_byte(b, "M", "mid M");
        uart_recv_byte(b); expect_byte(b, "I", "mid I");
        uart_recv_byte(b); expect_byte(b, "D", "mid D");
        uart_recv_byte(b); expect_byte(b, "=", "mid eq");
        uart_recv_byte(b); expect_byte(b, "0", "mid value");
        uart_recv_byte(b); expect_byte(b, ",", "mid comma");
        uart_recv_byte(b); expect_byte(b, "F", "mode F");
        uart_recv_byte(b); expect_byte(b, "U", "mode U");
        uart_recv_byte(b); expect_byte(b, "L", "mode L");
        uart_recv_byte(b); expect_byte(b, "L", "mode L2");
        uart_recv_byte(b); expect_byte(b, ",", "mode comma");
        uart_recv_byte(b); expect_byte(b, "S", "spwr S");
        uart_recv_byte(b); expect_byte(b, "P", "spwr P");
        uart_recv_byte(b); expect_byte(b, "W", "spwr W");
        uart_recv_byte(b); expect_byte(b, "R", "spwr R");
        uart_recv_byte(b); expect_byte(b, "=", "spwr eq");
        uart_recv_byte(b); expect_byte(b, "1", "spwr value");
        uart_recv_byte(b); expect_byte(b, ",", "spwr comma");
        uart_recv_byte(b); expect_byte(b, "T", "txn T");
        uart_recv_byte(b); expect_byte(b, "X", "txn X");
        uart_recv_byte(b); expect_byte(b, "N", "txn N");
        uart_recv_byte(b); expect_byte(b, "=", "txn eq");
        uart_recv_byte(b); expect_byte(b, "3", "txn high");
        uart_recv_byte(b); expect_byte(b, "C", "txn low");
        uart_recv_byte(b); expect_byte(b, 8'h0A, "hdr nl");

        uart_recv_byte(b); expect_byte(b, "C", "ch1 C");
        uart_recv_byte(b); expect_byte(b, "H", "ch1 H");
        uart_recv_byte(b); expect_byte(b, "1", "ch1 1");
        uart_recv_byte(b); expect_byte(b, ",", "ch1 comma 0");
        uart_recv_byte(b); expect_byte(b, "R", "ch1 R");
        uart_recv_byte(b); expect_byte(b, "A", "ch1 A");
        uart_recv_byte(b); expect_byte(b, "W", "ch1 W");
        uart_recv_byte(b); expect_byte(b, ",", "ch1 comma 1");
        uart_recv_byte(b); expect_byte(b, "1", "ch1 count 1");
        uart_recv_byte(b); expect_byte(b, "2", "ch1 count 2");
        uart_recv_byte(b); expect_byte(b, "8", "ch1 count 8");
        uart_recv_byte(b); expect_byte(b, ",", "ch1 comma 2");
        for (i = 0; i < 128; i = i + 1) begin
            uart_recv_byte(b); expect_byte(b, "1", "ch1 hex0");
            uart_recv_byte(b); expect_byte(b, "2", "ch1 hex1");
            uart_recv_byte(b); expect_byte(b, "3", "ch1 hex2");
            uart_recv_byte(b); expect_byte(b, "4", "ch1 hex3");
            if (i < 127) begin
                uart_recv_byte(b); expect_byte(b, ",", "ch1 sample comma");
            end
        end
        uart_recv_byte(b); expect_byte(b, 8'h0A, "ch1 nl");

        uart_recv_byte(b); expect_byte(b, "C", "ch2 C");
        uart_recv_byte(b); expect_byte(b, "H", "ch2 H");
        uart_recv_byte(b); expect_byte(b, "2", "ch2 2");
        uart_recv_byte(b); expect_byte(b, ",", "ch2 comma 0");
        uart_recv_byte(b); expect_byte(b, "R", "ch2 R");
        uart_recv_byte(b); expect_byte(b, "A", "ch2 A");
        uart_recv_byte(b); expect_byte(b, "W", "ch2 W");
        uart_recv_byte(b); expect_byte(b, ",", "ch2 comma 1");
        uart_recv_byte(b); expect_byte(b, "1", "ch2 count 1");
        uart_recv_byte(b); expect_byte(b, "2", "ch2 count 2");
        uart_recv_byte(b); expect_byte(b, "8", "ch2 count 8");
        uart_recv_byte(b); expect_byte(b, ",", "ch2 comma 2");
        for (i = 0; i < 128; i = i + 1) begin
            uart_recv_byte(b); expect_byte(b, "5", "ch2 hex0");
            uart_recv_byte(b); expect_byte(b, "6", "ch2 hex1");
            uart_recv_byte(b); expect_byte(b, "7", "ch2 hex2");
            uart_recv_byte(b); expect_byte(b, "8", "ch2 hex3");
            if (i < 127) begin
                uart_recv_byte(b); expect_byte(b, ",", "ch2 sample comma");
            end
        end
        uart_recv_byte(b); expect_byte(b, 8'h0A, "ch2 nl");

        $display("PASS: ASCII UART frame looks correct");
        $finish;
    end

endmodule
