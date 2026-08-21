// Real DFFs injected to satisfy Icarus elaboration and memory allocation
module DFF(CK, Q, D); input CK, D; output reg Q; always @(posedge CK) Q <= D; endmodule
module dff(CK, Q, D); input CK, D; output reg Q; always @(posedge CK) Q <= D; endmodule
