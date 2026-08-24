#include <algorithm>
#include <bits/stdc++.h>
#include <functional>
#include <numeric>
#include <queue>
#include <string_view>
#include <vector>
using namespace std;
class Solution {
public:
  int maxEqualSum(vector<int> &s1, vector<int> &s2, vector<int> &s3) {
    // code here
    int sum1 = accumulate(s1.begin(), s1.end(), 0),
        sum2 = accumulate(s2.begin(), s2.end(), 0),
        sum3 = accumulate(s3.begin(), s2.end(), 0);

    int i = 0, j = 0, k = 0;
    int n1 = s1.size(), n2 = s2.size(), n3 = s3.size();
    while (i < n1 && j < n2 && k < n3) {
      if (sum1 == sum2 && sum2 == sum3) {
        return sum1;
      }
      int maxi = max({sum1, sum2, sum3});
      if (maxi == sum1) {
        sum1 -= s1[i++];
      } else if (maxi == sum2) {
        sum2 -= s2[j++];
      } else {
        sum3 -= s3[k++];
      }
    }
    return 0;
  }
};