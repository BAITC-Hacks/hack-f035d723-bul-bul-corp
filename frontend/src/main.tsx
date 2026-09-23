import "@fontsource-variable/manrope";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { DemoSessionProvider } from "./app/DemoSession";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DemoSessionProvider>
        <App />
      </DemoSessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
