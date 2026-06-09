module pixel_clock_divider #(
    parameter integer HALF_DIVIDE = 11
) (
    input  wire clk_in,
    output reg  clk_out = 1'b0
);
    localparam integer COUNTER_WIDTH = (HALF_DIVIDE <= 1) ? 1 : $clog2(HALF_DIVIDE);

    reg [COUNTER_WIDTH-1:0] counter = {COUNTER_WIDTH{1'b0}};

    always @(posedge clk_in) begin
        if (counter == HALF_DIVIDE - 1) begin
            counter <= {COUNTER_WIDTH{1'b0}};
            clk_out <= ~clk_out;
        end else begin
            counter <= counter + 1'b1;
        end
    end
endmodule

