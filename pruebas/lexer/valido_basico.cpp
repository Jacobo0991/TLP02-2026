#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
#define MOD 1000000007

const ll INF = 1e18;

ll potencia(ll b, ll e) {
    ll r = 1;
    while (e > 0) {
        if (e & 1) r = r * b % MOD;
        b = b * b % MOD;
        e >>= 1;
    }
    return r;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    cin >> n;
    vector<int> a(n);
    for (auto &x : a) cin >> x;
    sort(a.begin(), a.end());
    cout << a[0] << " " << potencia(2, n) << '\n';
    return 0;
}
