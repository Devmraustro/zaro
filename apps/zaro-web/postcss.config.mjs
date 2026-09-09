// Tailwind CSS v4 is compiled through its PostCSS plugin. Without this
// config Next.js emits globals.css verbatim: `@import "tailwindcss"` is
// inlined unprocessed, `@theme` never compiles to `:root` variables, and
// zero utilities are generated -- the deployed pages render unstyled.
const postcssConfig = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default postcssConfig;
