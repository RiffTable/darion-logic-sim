// engine/Profile.h
#ifndef PROFILE_H
#define PROFILE_H
#include <vector>

struct Profile {
    void* target;
    int index;
    int output;
    Profile() : target(NULL), output(0){}
    Profile(void* t, int i, int o) : target(t),index(i), output(o){}
};
struct CPP_Gate {
    void* gate;
    uint8_t type;
    uint8_t output;
    uint8_t value;
    uint8_t scheduled;
    uint16_t book[4];
    std::vector<Profile> hitlist;
    CPP_Gate() : gate(NULL), type(0), output(3), value(0), scheduled(0){
        book[0] = book[1] = book[2] = book[3] = 0;
    }
    CPP_Gate(void* g, uint8_t t) : gate(g), type(t){
        book[0] = book[1] = book[2] = book[3] = 0;
        output = 3;
        value = 0;
        scheduled = 0;
    }
};
#endif