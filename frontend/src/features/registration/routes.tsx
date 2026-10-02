import { Navigate, type RouteObject } from "react-router-dom";
import { CompanyRegistrationPage } from "@/features/company/components/CompanyRegistrationPage";
import { AccessRequestPage } from "./components/AccessRequestPage";
import { RegisterRoleSelector } from "./components/RegisterRoleSelector";

/** Inscription publique (tâche 5.10) : choix du profil, puis le formulaire de ce profil. */
export const registrationRoutes: RouteObject[] = [
  { path: "/inscription", element: <RegisterRoleSelector /> },
  { path: "/inscription/entreprise", element: <CompanyRegistrationPage /> },
  { path: "/inscription/investisseur", element: <AccessRequestPage profil="investisseur" /> },
  { path: "/inscription/chercheur", element: <AccessRequestPage profil="chercheur" /> },
  // Ancienne adresse de l'inscription d'une entreprise (liens existants).
  { path: "/inscription-entreprise", element: <Navigate to="/inscription/entreprise" replace /> },
];
