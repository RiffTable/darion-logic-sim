// reactor/Profile.h
#ifndef PROFILE_H
#define PROFILE_H
#include <vector>
#include <stdint.h>
#include <cstddef>   // offsetof

struct CPP_Gate;

struct Profile {
    CPP_Gate* target;
    uint8_t index;
    uint8_t output;
    Profile() : target(nullptr), index(0), output(0){}
    Profile(CPP_Gate* t, uint8_t i, uint8_t o) : target(t),index(i), output(o){}
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
    // ── HOT SCALARS (12 B, all read in the inner propagate/sweep loop) ────────
    // Packed into bytes 0–11 so a single 64-B cache-line fetch covers every
    // field needed before touching hitlist.
    //
    //   offset  0: type         (int8_t,  1 B)
    //   offset  1: output       (uint8_t, 1 B)
    //   offset  2: inputlimit   (uint8_t, 1 B)
    //   offset  3: flags        (uint8_t, 1 B)
    //   offset  4: book[3]      (uint8_t, 3 B)
    //   offset  7: invalid (uint8_t, 1 B)
    //   offset  8: target_time  (uint32_t, 4 B)
    //   offset 12: [4 B natural padding to align 8-B hitlist pointer]
    // ── COLD / LARGE (offset 16) ──────────────────────────────────────────────
    //   offset 16: hitlist      (std::vector<Profile>, 24 B: ptr+size+capacity)
    //   → hitlist.data() lives on the heap; prefetch it explicitly.
    int8_t       type;
    uint8_t      output;
    uint8_t      inputlimit;
    uint8_t      flags;
    uint8_t      book[3];
    uint8_t      invalid;
    unsigned int target_time;    // moved before hitlist — stays in hot cacheline
    std::vector<Profile> hitlist; // 24 B; out-of-line data prefetched separately

    CPP_Gate() : type(0), output(2), inputlimit(2), flags(8), invalid(2), target_time(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
    CPP_Gate(uint8_t t, uint8_t lim) : type(t), output(2), inputlimit(lim), flags(8), invalid(lim), target_time(0), hitlist() {
        book[0] = book[1] = book[2] = 0;
    }
};

// Compile-time assertion: hot scalars must all fit before the hitlist pointer.
// If the struct layout ever drifts, this will fail at compile time.
static_assert(offsetof(CPP_Gate, hitlist) >= 12,
    "CPP_Gate: hot scalars overflowed into hitlist — check field order");
#endif