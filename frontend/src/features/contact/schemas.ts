import { z } from "zod";

export const contactFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Indiquez votre nom (2 caractères minimum).")
    .max(100, "Le nom ne doit pas dépasser 100 caractères."),
  email: z.string().trim().email("Indiquez une adresse e-mail valide."),
  subject: z
    .string()
    .trim()
    .min(3, "Précisez le sujet de votre demande (3 caractères minimum).")
    .max(150, "Le sujet ne doit pas dépasser 150 caractères."),
  message: z
    .string()
    .trim()
    .min(20, "Décrivez votre demande en au moins 20 caractères.")
    .max(5_000, "Le message ne doit pas dépasser 5 000 caractères."),
});

export type ContactForm = z.infer<typeof contactFormSchema>;
