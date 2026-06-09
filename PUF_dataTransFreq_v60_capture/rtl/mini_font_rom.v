`timescale 1ns / 1ps

module mini_font_rom (
    input  wire [7:0] char_code,
    input  wire [2:0] pixel_x,
    input  wire [3:0] pixel_y,
    output wire       pixel_on
);
    reg [7:0] glyph_bits;

    always @(*) begin
        case (char_code)
            "0": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01101110;
                    3'd3: glyph_bits = 8'b01110110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "1": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00011000;
                    3'd1: glyph_bits = 8'b00111000;
                    3'd2: glyph_bits = 8'b00011000;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    3'd5: glyph_bits = 8'b00011000;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "2": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b00000110;
                    3'd3: glyph_bits = 8'b00001100;
                    3'd4: glyph_bits = 8'b00110000;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b01111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "3": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b00000110;
                    3'd3: glyph_bits = 8'b00011100;
                    3'd4: glyph_bits = 8'b00000110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "4": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00001100;
                    3'd1: glyph_bits = 8'b00011100;
                    3'd2: glyph_bits = 8'b00101100;
                    3'd3: glyph_bits = 8'b01001100;
                    3'd4: glyph_bits = 8'b01111110;
                    3'd5: glyph_bits = 8'b00001100;
                    3'd6: glyph_bits = 8'b00001100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "5": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111110;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01111100;
                    3'd3: glyph_bits = 8'b00000110;
                    3'd4: glyph_bits = 8'b00000110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "6": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "7": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111110;
                    3'd1: glyph_bits = 8'b00000110;
                    3'd2: glyph_bits = 8'b00001100;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00110000;
                    3'd5: glyph_bits = 8'b00110000;
                    3'd6: glyph_bits = 8'b00110000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "8": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b00111100;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "9": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b00111110;
                    3'd4: glyph_bits = 8'b00000110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "A": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00011000;
                    3'd1: glyph_bits = 8'b00111100;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01111110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "B": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b01111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "C": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01100000;
                    3'd4: glyph_bits = 8'b01100000;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "D": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111000;
                    3'd1: glyph_bits = 8'b01101100;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01101100;
                    3'd6: glyph_bits = 8'b01111000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "E": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111110;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01100000;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b01111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "F": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111110;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01100000;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b01100000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "G": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01101110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "H": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01111110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "I": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b00011000;
                    3'd2: glyph_bits = 8'b00011000;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    3'd5: glyph_bits = 8'b00011000;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "K": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01101100;
                    3'd2: glyph_bits = 8'b01111000;
                    3'd3: glyph_bits = 8'b01110000;
                    3'd4: glyph_bits = 8'b01111000;
                    3'd5: glyph_bits = 8'b01101100;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "L": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100000;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b01100000;
                    3'd4: glyph_bits = 8'b01100000;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b01111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "M": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100011;
                    3'd1: glyph_bits = 8'b01110111;
                    3'd2: glyph_bits = 8'b01111111;
                    3'd3: glyph_bits = 8'b01101011;
                    3'd4: glyph_bits = 8'b01100011;
                    3'd5: glyph_bits = 8'b01100011;
                    3'd6: glyph_bits = 8'b01100011;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "N": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01110110;
                    3'd2: glyph_bits = 8'b01111110;
                    3'd3: glyph_bits = 8'b01111110;
                    3'd4: glyph_bits = 8'b01101110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "O": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "P": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01100000;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b01100000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "R": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01111100;
                    3'd4: glyph_bits = 8'b01111000;
                    3'd5: glyph_bits = 8'b01101100;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "S": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100000;
                    3'd3: glyph_bits = 8'b00111100;
                    3'd4: glyph_bits = 8'b00000110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "T": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01111110;
                    3'd1: glyph_bits = 8'b00011000;
                    3'd2: glyph_bits = 8'b00011000;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    3'd5: glyph_bits = 8'b00011000;
                    3'd6: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "U": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "_": begin
                case (pixel_y[3:1])
                    3'd7: glyph_bits = 8'b01111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "[": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b00110000;
                    3'd2: glyph_bits = 8'b00110000;
                    3'd3: glyph_bits = 8'b00110000;
                    3'd4: glyph_bits = 8'b00110000;
                    3'd5: glyph_bits = 8'b00110000;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "]": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b00001100;
                    3'd2: glyph_bits = 8'b00001100;
                    3'd3: glyph_bits = 8'b00001100;
                    3'd4: glyph_bits = 8'b00001100;
                    3'd5: glyph_bits = 8'b00001100;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "b": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100000;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01111100;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b01111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "e": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b00111100;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01111110;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "l": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00011000;
                    3'd1: glyph_bits = 8'b00011000;
                    3'd2: glyph_bits = 8'b00011000;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    3'd5: glyph_bits = 8'b00011000;
                    3'd6: glyph_bits = 8'b00001100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "o": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b00111100;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "u": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b01100110;
                    3'd6: glyph_bits = 8'b00111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "w": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b01100011;
                    3'd3: glyph_bits = 8'b01100011;
                    3'd4: glyph_bits = 8'b01101011;
                    3'd5: glyph_bits = 8'b01111111;
                    3'd6: glyph_bits = 8'b00110110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "y": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b00111110;
                    3'd5: glyph_bits = 8'b00000110;
                    3'd6: glyph_bits = 8'b00111100;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "k": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100000;
                    3'd1: glyph_bits = 8'b01100000;
                    3'd2: glyph_bits = 8'b01101100;
                    3'd3: glyph_bits = 8'b01111000;
                    3'd4: glyph_bits = 8'b01110000;
                    3'd5: glyph_bits = 8'b01101100;
                    3'd6: glyph_bits = 8'b01100110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "V": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b01100110;
                    3'd3: glyph_bits = 8'b01100110;
                    3'd4: glyph_bits = 8'b01100110;
                    3'd5: glyph_bits = 8'b00111100;
                    3'd6: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "W": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100011;
                    3'd1: glyph_bits = 8'b01100011;
                    3'd2: glyph_bits = 8'b01100011;
                    3'd3: glyph_bits = 8'b01101011;
                    3'd4: glyph_bits = 8'b01101011;
                    3'd5: glyph_bits = 8'b01111111;
                    3'd6: glyph_bits = 8'b00110110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "Y": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b01100110;
                    3'd1: glyph_bits = 8'b01100110;
                    3'd2: glyph_bits = 8'b00111100;
                    3'd3: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    3'd5: glyph_bits = 8'b00011000;
                    3'd6: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "@": begin
                case (pixel_y[3:1])
                    3'd0: glyph_bits = 8'b00111100;
                    3'd1: glyph_bits = 8'b01100011;
                    3'd2: glyph_bits = 8'b01101111;
                    3'd3: glyph_bits = 8'b01101111;
                    3'd4: glyph_bits = 8'b01101110;
                    3'd5: glyph_bits = 8'b01100000;
                    3'd6: glyph_bits = 8'b00111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "+": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b00011000;
                    3'd3: glyph_bits = 8'b01111110;
                    3'd4: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            ":": begin
                case (pixel_y[3:1])
                    3'd2: glyph_bits = 8'b00011000;
                    3'd4: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            "-": begin
                case (pixel_y[3:1])
                    3'd3: glyph_bits = 8'b01111110;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            ".": begin
                case (pixel_y[3:1])
                    3'd6: glyph_bits = 8'b00011000;
                    default: glyph_bits = 8'b00000000;
                endcase
            end
            default: glyph_bits = 8'b00000000;
        endcase
    end

    assign pixel_on = glyph_bits[7 - pixel_x];
endmodule
