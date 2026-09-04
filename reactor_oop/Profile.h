// reactor_oop/Profile.h
#ifndef PROFILE_H
#define PROFILE_H
#include <vector>
#include <stdint.h>
#include <cstddef>

struct Profile {
    void* target; // this will hold CPP_Gate* instead of Python Gate object
    int index;
    int output;
    Profile() : target(NULL), index(0), output(0){}
    Profile(void* t, int i, int o) : target(t), index(i), output(o){}
};

struct CPP_Gate {
    void*   gate;      // pointer back to python Gate
    uint8_t type;
    uint8_t output;
    uint8_t inputlimit;
    uint8_t value;
    uint8_t scheduled;
    uint16_t book[3];
    std::vector<Profile> hitlist;

    CPP_Gate() : gate(NULL), type(0), output(2), inputlimit(2), value(0), scheduled(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
    CPP_Gate(void* g, uint8_t t, uint8_t lim) : gate(g), type(t), output(2), inputlimit(lim), value(0), scheduled(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
};
#endif