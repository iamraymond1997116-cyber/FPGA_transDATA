#include "verilated.h"
#include "Vtb_trigger_chain.h"

double sc_time_stamp() { return 0; }

int main(int argc, char** argv) {
    VerilatedContext* contextp = new VerilatedContext;
    contextp->commandArgs(argc, argv);
    Vtb_trigger_chain* top = new Vtb_trigger_chain{contextp};

    while (!contextp->gotFinish()) {
        top->eval();
    }

    top->final();
    delete top;
    delete contextp;
    return 0;
}
