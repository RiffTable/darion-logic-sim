// reactor_oop/Profile.h
#ifndef PROFILE_H
#define PROFILE_H
#include <vector>
#include <stdint.h>
#include <cstddef>

struct CPP_Gate;

struct Profile {
    CPP_Gate* target; // this will hold CPP_Gate* instead of Python Gate object
    int index;
    int output;
    Profile() : target(NULL), index(0), output(0){}
    Profile(CPP_Gate* t, int i, int o) : target(t), index(i), output(o){}
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
    void*   gate;      // pointer back to python Gate
    uint8_t type;
    uint8_t output;
    uint8_t inputlimit;
    uint8_t value;     // keeping for backwards compatibility
    uint8_t scheduled; // keeping for backwards compatibility
    uint8_t flags;
    uint8_t book[3];
    uint8_t invalid;
    unsigned int target_time;
    std::vector<Profile> hitlist;

    CPP_Gate() : gate(NULL), type(0), output(2), inputlimit(2), value(0), scheduled(0), flags(8), invalid(2), target_time(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
    CPP_Gate(void* g, uint8_t t, uint8_t lim) : gate(g), type(t), output(2), inputlimit(lim), value(0), scheduled(0), flags(8), invalid(lim), target_time(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
};
#endif