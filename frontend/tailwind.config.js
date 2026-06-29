/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F1E7",      // papel cálido, fondo general
        ink: "#1B2A41",        // tinta azul oscura, casi negra
        ledger: "#2F4858",     // azul petróleo, acentos y burbujas propias
        stamp: "#A8442E",      // rojo sello/timbre, para fuentes citadas y alertas
        brass: "#C9A24B",      // dorado latón, detalles y bordes activos
        line: "#D8CDB8"        // líneas/hairlines sobre el papel
      },
      fontFamily: {
        display: ["'Source Serif 4'", "Georgia", "serif"],
        body: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"]
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
