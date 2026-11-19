#include <bits/stdc++.h>
using namespace std;

typedef long long ll;
#define LIMITE 100

struct Punto {
    int x, y;
};

ll sumar(ll a, ll b) {
    return a + b;
}

int main() {
    int numeros[3] = {1, 2, 3};
    vector<int> v = {4, 5, 6};
    int total = numeros[0];
    for (auto &item : v) {
        total += item;
    }
    Punto p;
    p.x = total;
    p.y = 20;
    Punto *ptr = &p;
    cout << ptr->x << " " << sumar(10, 20) << '\n';
    return 0;
}
