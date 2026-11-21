import React from "react";
import RasAppCore from "React-Automation-Studio/components/SystemComponents/RasAppCore";
import themes, { defaultTheme } from "./theme";
import AppRoutes from "./AppRoutes";

const App = () => (
  <RasAppCore themes={themes} defaultTheme={defaultTheme}>
    <AppRoutes />
  </RasAppCore>
);

export default App;
