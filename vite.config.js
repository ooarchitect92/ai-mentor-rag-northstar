import { defineConfig } from "vite";
import { resolve } from "node:path";

const root = process.cwd();

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        home: resolve(root, "index.html"),
        programs: resolve(root, "programs/index.html"),
        cma: resolve(root, "cma-usa-course-details/index.html"),
        cpa: resolve(root, "cpa-course-details/index.html"),
        acca: resolve(root, "acca-course-details/index.html"),
        about: resolve(root, "about-us/index.html"),
        admissions: resolve(root, "admissions/index.html"),
        contact: resolve(root, "contact-us/index.html"),
        insights: resolve(root, "insights/index.html"),
        notFound: resolve(root, "404.html")
      }
    }
  }
});