import React from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import ProtectedRoute from "React-Automation-Studio/components/SystemComponents/ProtectedRoute";
import AllDevices from "./pages/AllDevices";

const AppRoutes = () => (
  <BrowserRouter>
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AllDevices />
          </ProtectedRoute>
        }
      />
    </Routes>
  </BrowserRouter>
);

export default AppRoutes;
