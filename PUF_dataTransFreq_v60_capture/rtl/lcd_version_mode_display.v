// ============================================================================
// lcd_version_mode_display — LCD shows V6.x version + all 5 mode names
//
// Layout (6 lines, 60x17 char grid, 8x16 font):
//   Row 4  (y=64-79):   V6.1
//   Row 6  (y=96-111):  MODE_FULL
//   Row 8  (y=128-143): MODE_POS_CUT
//   Row 10 (y=160-175): MODE_NEG_CUT
//   Row 12 (y=192-207): MODE_EXTREMA_CYCLE
//   Row 14 (y=224-239): MODE_FULL_CYCLE
// ============================================================================
`timescale 1ns / 1ps

module lcd_version_mode_display #(
    parameter [7:0] VERSION_MAJOR = 8'd6,
    parameter [7:0] VERSION_MINOR = 8'd1
) (
    input  wire        pixel_clk,
    input  wire        rst_n,
    input  wire [2:0]  mode,
    output wire        lcd_hs,
    output wire        lcd_vs,
    output wire        lcd_de,
    output wire [7:0]  lcd_r,
    output wire [7:0]  lcd_g,
    output wire [7:0]  lcd_b
);

    wire [11:0] pixel_x;
    wire [11:0] pixel_y;
    lcd_timing timing (
        .clk(pixel_clk), .hs(lcd_hs), .vs(lcd_vs), .de(lcd_de),
        .pixel_x(pixel_x), .pixel_y(pixel_y)
    );

    wire [5:0] char_col        = pixel_x[11:3];
    wire [2:0] pixel_x_in_char = pixel_x[2:0];
    wire [3:0] char_row_idx    = pixel_y[7:4];   // which character row (0-16)
    wire [3:0] char_row        = pixel_y[3:0];   // pixel within char (0-15)

    // ── Which text row are we in? ──────────────────────────────────
    wire in_v    = (char_row_idx == 4'd4);
    wire in_full = (char_row_idx == 4'd6);
    wire in_pcut = (char_row_idx == 4'd8);
    wire in_ncut = (char_row_idx == 4'd10);
    wire in_extr = (char_row_idx == 4'd12);
    wire in_fcyc = (char_row_idx == 4'd14);
    wire any_row = in_v || in_full || in_pcut || in_ncut || in_extr || in_fcyc;

    // ── Character lookup per row ───────────────────────────────────
    reg [7:0] disp_char;
    always @(*) begin
        disp_char = " ";  // default blank

        if (char_row_idx == 4'd4) begin
            // "V6.1" at col 28..31
            case (char_col)
                6'd28: disp_char = "V";
                6'd29: disp_char = 8'd48 + VERSION_MAJOR[3:0];
                6'd30: disp_char = ".";
                6'd31: disp_char = 8'd48 + VERSION_MINOR[3:0];
            endcase
        end
        else if (char_row_idx == 4'd6) begin
            // "MODE_FULL" at col 25..33 (9 chars, centre=25)
            case (char_col)
                6'd25: disp_char = "M";
                6'd26: disp_char = "O";
                6'd27: disp_char = "D";
                6'd28: disp_char = "E";
                6'd29: disp_char = "_";
                6'd30: disp_char = "F";
                6'd31: disp_char = "U";
                6'd32: disp_char = "L";
                6'd33: disp_char = "L";
            endcase
        end
        else if (char_row_idx == 4'd8) begin
            // "MODE_POS_CUT" at col 24..35 (12 chars, centre=24)
            case (char_col)
                6'd24: disp_char = "M";
                6'd25: disp_char = "O";
                6'd26: disp_char = "D";
                6'd27: disp_char = "E";
                6'd28: disp_char = "_";
                6'd29: disp_char = "P";
                6'd30: disp_char = "O";
                6'd31: disp_char = "S";
                6'd32: disp_char = "_";
                6'd33: disp_char = "C";
                6'd34: disp_char = "U";
                6'd35: disp_char = "T";
            endcase
        end
        else if (char_row_idx == 4'd10) begin
            // "MODE_NEG_CUT" at col 24..35 (12 chars, centre=24)
            case (char_col)
                6'd24: disp_char = "M";
                6'd25: disp_char = "O";
                6'd26: disp_char = "D";
                6'd27: disp_char = "E";
                6'd28: disp_char = "_";
                6'd29: disp_char = "N";
                6'd30: disp_char = "E";
                6'd31: disp_char = "G";
                6'd32: disp_char = "_";
                6'd33: disp_char = "C";
                6'd34: disp_char = "U";
                6'd35: disp_char = "T";
            endcase
        end
        else if (char_row_idx == 4'd12) begin
            // "MODE_EXTREMA_CYCLE" at col 21..38 (18 chars, centre=21)
            case (char_col)
                6'd21: disp_char = "M";
                6'd22: disp_char = "O";
                6'd23: disp_char = "D";
                6'd24: disp_char = "E";
                6'd25: disp_char = "_";
                6'd26: disp_char = "E";
                6'd27: disp_char = "X";
                6'd28: disp_char = "T";
                6'd29: disp_char = "R";
                6'd30: disp_char = "E";
                6'd31: disp_char = "M";
                6'd32: disp_char = "A";
                6'd33: disp_char = "_";
                6'd34: disp_char = "C";
                6'd35: disp_char = "Y";
                6'd36: disp_char = "C";
                6'd37: disp_char = "L";
                6'd38: disp_char = "E";  // 21: E, 37: E = 17 chars
            endcase
        end
        else if (char_row_idx == 4'd14) begin
            // "MODE_FULL_CYCLE" at col 22..36 (15 chars, centre=22)
            case (char_col)
                6'd22: disp_char = "M";
                6'd23: disp_char = "O";
                6'd24: disp_char = "D";
                6'd25: disp_char = "E";
                6'd26: disp_char = "_";
                6'd27: disp_char = "F";
                6'd28: disp_char = "U";
                6'd29: disp_char = "L";
                6'd30: disp_char = "L";
                6'd31: disp_char = "_";
                6'd32: disp_char = "C";
                6'd33: disp_char = "Y";
                6'd34: disp_char = "C";
                6'd35: disp_char = "L";
                6'd36: disp_char = "E";
            endcase
        end
    end

    // ── Font ROM ──────────────────────────────────────────────────
    wire font_pixel_on;
    mini_font_rom font_rom (
        .char_code (disp_char),
        .pixel_x   (pixel_x_in_char),
        .pixel_y   (char_row),
        .pixel_on  (font_pixel_on)
    );

    wire text_on = font_pixel_on && any_row;

    assign lcd_r = !lcd_de ? 8'd0 : text_on ? 8'd255 : 8'd0;
    assign lcd_g = !lcd_de ? 8'd0 : text_on ? 8'd255 : 8'd0;
    assign lcd_b = !lcd_de ? 8'd0 : text_on ? 8'd255 : 8'd0;

endmodule
