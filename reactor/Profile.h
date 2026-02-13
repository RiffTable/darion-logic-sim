// engine/Profile.h
#ifndef PROFILE_H
#define PROFILE_H

#include <vector>

struct Profile {
    void* target;
    int index;
    int output;
    // bool red_flag;
    Profile() : target(NULL), output(0){}
    Profile(void* t, int i, int o) : target(t),index(i), output(o){}
};

#endif