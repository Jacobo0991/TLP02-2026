struct Arista {
    int u, v, w;
    bool operator<(const Arista &o) const { return w < o.w; }
};

struct Nodo {
    int val;
    Nodo *izq, *der;
    Nodo(int v) : val(v), izq(nullptr), der(nullptr) {}
};

Nodo *insertar(Nodo *r, int v) {
    if (r == nullptr) return new Nodo(v);
    if (v < r->val) r->izq = insertar(r->izq, v);
    else r->der = insertar(r->der, v);
    return r;
}
