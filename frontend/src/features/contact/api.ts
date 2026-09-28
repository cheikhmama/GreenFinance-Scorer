import { useMutation } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import { sendContactMessage } from "@/shared/api/generated/contact/contact";
import type { ContactForm } from "./schemas";

export function useSendContactMessage() {
  return useMutation<void, ApiError, ContactForm>({
    mutationFn: (payload) => sendContactMessage(payload),
    retry: false,
  });
}
