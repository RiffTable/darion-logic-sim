// reactor/Profile.h
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

// ─── Task ─────────────────────────────────────────────────────────────────
struct Task {
    int      gate_loc;
    unsigned int time;
    int      location;
    Task() : gate_loc(-1), time(0), location(0) {}
    Task(int g, unsigned int t, int loc) : gate_loc(g), time(t), location(loc) {}
    bool operator>(const Task& other) const {
        if (time != other.time) return time > other.time;
        return location > other.location;
    }
};
// ──────────────────────────────────────────────────────────────────────────

// Bitmask Definitions
enum GateFlags : uint8_t {
    FLAG_VALUE     = 1 << 0, // Bit 0 (Dec: 1)
    FLAG_SCHEDULED = 1 << 1, // Bit 1 (Dec: 2)
    FLAG_MARK      = 1 << 2, // Bit 2 (Dec: 4)
    FLAG_UPDATE    = 1 << 3  // Bit 3 (Dec: 8)
};

struct CPP_Gate {
    int8_t type;
    uint8_t output;
    uint8_t inputlimit;
    uint8_t flags;
    uint8_t book[3];
    int edge_start;
    int edge_length;
    unsigned int target_time;

    // FIXED: output and inputlimit now come before flags in the init list
    CPP_Gate() : type(0), output(2), inputlimit(2), flags(0), edge_start(0), edge_length(0), target_time(0) {
        book[0] = book[1] = book[2] = 0;
    }

    // FIXED: output and inputlimit now come before flags in the init list
    CPP_Gate(uint8_t t, uint8_t lim) : type(t), output(2), inputlimit(lim), flags(0), edge_start(0), edge_length(0), target_time(0) {
        book[0] = book[1] = book[2] = 0;
    }
};
#endif