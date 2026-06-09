module lcd_timing #(
    parameter integer H_ACTIVE = 480,
    parameter integer H_FP     = 2,
    parameter integer H_SYNC   = 41,
    parameter integer H_BP     = 2,
    parameter integer V_ACTIVE = 272,
    parameter integer V_FP     = 2,
    parameter integer V_SYNC   = 10,
    parameter integer V_BP     = 2,
    parameter         HS_POL   = 1'b0,
    parameter         VS_POL   = 1'b0
) (
    input  wire        clk,
    output wire        hs,
    output wire        vs,
    output wire        de,
    output wire [11:0] pixel_x,
    output wire [11:0] pixel_y
);
    localparam integer H_TOTAL = H_ACTIVE + H_FP + H_SYNC + H_BP;
    localparam integer V_TOTAL = V_ACTIVE + V_FP + V_SYNC + V_BP;
    localparam integer H_COUNTER_WIDTH = (H_TOTAL <= 1) ? 1 : $clog2(H_TOTAL);
    localparam integer V_COUNTER_WIDTH = (V_TOTAL <= 1) ? 1 : $clog2(V_TOTAL);

    reg [H_COUNTER_WIDTH-1:0] h_count = {H_COUNTER_WIDTH{1'b0}};
    reg [V_COUNTER_WIDTH-1:0] v_count = {V_COUNTER_WIDTH{1'b0}};

    wire h_sync_window;
    wire v_sync_window;
    wire h_active_window;
    wire v_active_window;

    always @(posedge clk) begin
        if (h_count == H_TOTAL - 1) begin
            h_count <= {H_COUNTER_WIDTH{1'b0}};
            if (v_count == V_TOTAL - 1) begin
                v_count <= {V_COUNTER_WIDTH{1'b0}};
            end else begin
                v_count <= v_count + 1'b1;
            end
        end else begin
            h_count <= h_count + 1'b1;
        end
    end

    assign h_sync_window = (h_count >= H_FP) && (h_count < H_FP + H_SYNC);
    assign v_sync_window = (v_count >= V_FP) && (v_count < V_FP + V_SYNC);
    assign h_active_window = (h_count >= H_FP + H_SYNC + H_BP) &&
                             (h_count < H_FP + H_SYNC + H_BP + H_ACTIVE);
    assign v_active_window = (v_count >= V_FP + V_SYNC + V_BP) &&
                             (v_count < V_FP + V_SYNC + V_BP + V_ACTIVE);

    assign hs = HS_POL ? h_sync_window : ~h_sync_window;
    assign vs = VS_POL ? v_sync_window : ~v_sync_window;
    assign de = h_active_window && v_active_window;
    assign pixel_x = h_active_window ? (h_count - (H_FP + H_SYNC + H_BP)) : 12'd0;
    assign pixel_y = v_active_window ? (v_count - (V_FP + V_SYNC + V_BP)) : 12'd0;
endmodule

