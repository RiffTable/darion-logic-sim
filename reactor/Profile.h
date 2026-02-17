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
    bool operator<(const Profile& other) const {
        if(target==other.target){
            return index<other.index;
        }
        return target < other.target;
    }
    void flag(){
        index=-index-1;
    }
};

#endif