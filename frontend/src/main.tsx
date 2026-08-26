import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { SessionProvider } from "./features/auth/session";
import "./index.css";
import { AppRouter } from "./router";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Application root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <AppRouter />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
