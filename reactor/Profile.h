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
// Scheduled propagation event for FLIPFLOP/clock mode.
// Used in a min-heap (std::priority_queue with greater<Task>).
//   gate_loc  – index into gate_infolist / gate_verse
//   time      – absolute simulation tick at which this fires
//   location  – topological rank used as tiebreaker (lower fires first)
struct Task {
    int      gate_loc;
    unsigned int time;
    int      location;
    Task() : gate_loc(-1), time(0), location(0) {}
    Task(int g, unsigned int t, int loc) : gate_loc(g), time(t), location(loc) {}
    // min-heap: smallest time first; ties broken by topological location
    bool operator>(const Task& other) const {
        if (time != other.time) return time > other.time;
        return location > other.location;
    }
};
// ──────────────────────────────────────────────────────────────────────────

struct CPP_Gate {
    int8_t type;
    uint8_t output;
    uint8_t value;
    uint8_t scheduled;
    uint8_t mark;
    uint8_t update;
    uint8_t inputlimit;
    uint8_t book[3];
    std::vector<Profile> hitlist;
    CPP_Gate() : type(0), output(2), value(0), scheduled(0), mark(0), update(1), inputlimit(2) {
        book[0] = book[1] = book[2] = 0;
    }
    CPP_Gate(uint8_t t, uint8_t lim) : type(t), inputlimit(lim) {
        book[0] = book[1] = book[2] = 0;
        output = 2;
        value = 0;
        scheduled = 0;
        mark = 0;
        update = 1;
    }
};
#endif