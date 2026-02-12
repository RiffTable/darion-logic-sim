// engine/Profile.h
#ifndef PROFILE_H
#define PROFILE_H

#include <vector>

struct Profile {
    void* target;
    std::vector<int> index;
    int output;
    bool red_flag;

    Profile() : target(NULL), output(0), red_flag(false) {}
    Profile(void* t, int i, int o) : target(t), output(o), red_flag(false) {
        index.push_back(i);
    }
};

#endif