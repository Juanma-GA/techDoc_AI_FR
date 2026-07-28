import { create } from "zustand";

/**
 * Garde de navigation generique : toute page avec des modifications non
 * sauvegardees enregistre un message ici (et le retire des qu'elle sauvegarde
 * / annule / se demonte). `App` l'utilise pour intercepter la navigation
 * (liens de la sidebar + fermeture d'onglet) et demander confirmation avant
 * de perdre les modifications — jamais via un popup natif (regle #2), une
 * UI maison s'en charge directement dans `App`.
 */
type UnsavedGuardState = {
  message: string | null;
  setGuard: (message: string | null) => void;
};

export const useUnsavedGuardStore = create<UnsavedGuardState>((set) => ({
  message: null,
  setGuard: (message) => set({ message }),
}));
