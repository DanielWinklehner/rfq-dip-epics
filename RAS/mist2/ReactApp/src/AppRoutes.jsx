import React from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import ProtectedRoute from "React-Automation-Studio/components/SystemComponents/ProtectedRoute";
import Probe from "React-Automation-Studio/components/SettingsPages/Probe";
import DeviceWindow from "./pages/DeviceWindow";
import MainWindow from "./pages/MainWindow";

// The routes of the MIST-2 GUI: the main window, one window per device
// (/device/<registry id>) and the RAS Probe of the context menu.
// ProtectedRoute lets everybody in while login is disabled (owner: no login).
const routes = [
  ["/", <MainWindow key="main" />],
  ["/device/:id", <DeviceWindow key="device" />],
  ["/Probe", <Probe key="probe" />],
];

const AppRoutes = () => (
  <BrowserRouter>
    <Routes>
      {routes.map(([path, element]) => (
        <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
      ))}
    </Routes>
  </BrowserRouter>
);

export default AppRoutes;
