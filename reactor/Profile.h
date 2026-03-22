// engine/Profile.h
#ifndef PROFILE_H
#define PROFILE_H
#include <vector>
#include <stdint.h>

struct Profile {
    int target;
    uint8_t index;
    uint8_t output;
    Profile() : target(-1), index(0), output(0){}
    Profile(int t, uint8_t i, uint8_t o) : target(t),index(i), output(o){}
    bool operator<(const Profile& other) const {
        return target < other.target;
    }
};
struct CPP_Gate {
    uint8_t type;
    uint8_t output;
    uint8_t value;
    uint8_t scheduled;
    uint16_t inputlimit;
    uint16_t book[4];
    std::vector<Profile> hitlist;
    CPP_Gate() : type(0), output(3), value(0), scheduled(0), inputlimit(2) {
        book[0] = book[1] = book[2] = book[3] = 0;
    }
    CPP_Gate(uint8_t t, uint16_t lim) : type(t), inputlimit(lim) {
        book[0] = book[1] = book[2] = book[3] = 0;
        output = 3;
        value = 0;
        scheduled = 0;
    }
};
#endif