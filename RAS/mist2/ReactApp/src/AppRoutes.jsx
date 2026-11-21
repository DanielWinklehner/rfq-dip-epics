import React from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import ProtectedRoute from "React-Automation-Studio/components/SystemComponents/ProtectedRoute";
import Mist2Main from "./pages/Mist2Main";

// The routes of the MIST-2 GUI. ProtectedRoute lets everybody in while login
// is disabled (VITE_EnableLogin=false) and enforces login once it is enabled.
const AppRoutes = () => (
  <BrowserRouter>
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Mist2Main />
          </ProtectedRoute>
        }
      />
    </Routes>
  </BrowserRouter>
);

export default AppRoutes;
