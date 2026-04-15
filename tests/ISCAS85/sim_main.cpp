#include <iostream>
#include <chrono>
#include "Vc6288.h" 
#include "verilated.h"

// Required by Verilator for time-tracking
double sc_time_stamp() { return 0; }

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    
    Vc6288* top = new Vc6288;

    const long VECTORS = 50000;      
    const long GATE_COUNT = 2416;    // Updated to exactly 2416 based on your file
    
    top->eval(); 

    auto start_time = std::chrono::high_resolution_clock::now();

    for (long i = 0; i < VECTORS; i++) {
        top->N1 = i % 2; 
        top->eval(); 
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duration = end_time - start_time;

    double total_evals = (double)GATE_COUNT * VECTORS; 
    double throughput = (total_evals / duration.count()) / 1000000.0;

    std::cout << "========================================\n";
    std::cout << " VERILATOR C++ BASELINE (CYCLE-BASED)   \n";
    std::cout << "========================================\n";
    std::cout << "Duration   : " << duration.count() << " seconds\n";
    std::cout << "Throughput : " << throughput << " ME/s\n";

    delete top;
    return 0;
}