// Errores intencionados para demostrar la detección y la recuperación.
int edad = 22;
int edad = 25;                 // redeclaración en el ámbito global
int cantidad = "veinticinco"; // tipo incompatible

struct Persona { int numero; };

int main() {
    int resultado = inexistente; // identificador no declarado
    Persona p;
    p.otraCosa = 1;             // miembro inexistente
    int *puntero = nullptr;
    puntero.numero = 3;         // '.' sobre puntero
    int n = nullptr;            // nullptr sobre int
    return "texto";             // retorno incompatible (int)
}
